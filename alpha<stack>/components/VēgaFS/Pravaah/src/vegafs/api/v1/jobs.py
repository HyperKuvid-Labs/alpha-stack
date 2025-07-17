from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
import asyncio # For background task dispatch

# Internal project imports
from vegafs.database import get_db_session # Assuming this is defined in vegafs/database.py
from vegafs.models.job import Job as JobModel, JobStatus as JobModelStatus # Assuming these models are in vegafs/models/job.py
from vegafs.core.processor import process_job_request # Assuming this function handles dispatching to Rust core

# region Pydantic Models

class JobStatusEnum(str, Enum):
    """
    Represents the possible states of a processing job.
    Maps directly to vegafs.models.job.JobStatus.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class JobCreate(BaseModel):
    """
    Request model for creating a new processing job.
    """
    operation_type: str = Field(..., description="The type of operation to perform (e.g., 'directory_analysis', 'file_transform').")
    target_path: str = Field(..., description="The primary path on which the operation will be performed (e.g., '/data/my_dir').")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional operation-specific parameters that are serialized as JSONB.")

class JobResponse(BaseModel):
    """
    Response model for retrieving job details.
    """
    job_id: UUID = Field(..., description="Unique identifier for the job.")
    operation_type: str = Field(..., description="The type of operation performed.")
    target_path: str = Field(..., description="The target path of the operation.")
    parameters: Optional[Dict[str, Any]] = Field(None, description="The parameters used for the operation.")
    status: JobStatusEnum = Field(..., description="Current status of the job.")
    created_at: datetime = Field(..., description="Timestamp when the job was created (UTC).")
    updated_at: datetime = Field(..., description="Timestamp when the job was last updated (UTC).")
    result: Optional[Dict[str, Any]] = Field(None, description="The results of the job, if completed successfully.")
    error_message: Optional[str] = Field(None, description="Error message if the job failed.")

    class Config:
        """Pydantic configuration for ORM mode."""
        from_attributes = True # Enable ORM mode for seamless conversion from SQLAlchemy models

# endregion

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new file processing job",
    description="Submit a new job to perform operations like directory analysis, file transformation, etc. The job is initially set to PENDING status and then dispatched for processing."
)
async def create_job(
    job_create: JobCreate,
    db: Session = Depends(get_db_session)
):
    """
    Create a new file processing job.

    - **operation_type**: The type of processing to perform (e.g., 'directory_analysis', 'file_transformation').
    - **target_path**: The file or directory path to operate on.
    - **parameters**: Optional dictionary for operation-specific parameters (e.g., search patterns, output format).
    """
    new_job_id = uuid4()
    now = datetime.utcnow()

    # Create job entry in database
    db_job = JobModel(
        job_id=new_job_id,
        operation_type=job_create.operation_type,
        target_path=job_create.target_path,
        parameters=job_create.parameters,
        status=JobModelStatus.PENDING, # Use the ORM's JobStatus Enum
        created_at=now,
        updated_at=now,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Dispatch job to background processing.
    # The 'process_job_request' function in vegafs.core.processor
    # will handle the actual interaction with the Rust core or queueing.
    asyncio.create_task(
        process_job_request(
            job_id=db_job.job_id,
            operation_type=db_job.operation_type,
            target_path=db_job.target_path,
            parameters=db_job.parameters,
            db_session=db # Pass the session or context needed by processor
        )
    )

    return JobResponse.from_orm(db_job)

@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve the status and details of a job",
    description="Get the current status, progress, and results (if completed) of a specific processing job."
)
async def get_job(
    job_id: UUID,
    db: Session = Depends(get_db_session)
):
    """
    Retrieve the status and details of a specific job by its ID.
    """
    job = db.query(JobModel).filter(JobModel.job_id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )

    return JobResponse.from_orm(job)

@router.get(
    "",
    response_model=List[JobResponse],
    summary="List all processing jobs",
    description="Retrieve a list of all submitted processing jobs with their current status. Supports optional filtering by status."
)
async def list_jobs(
    status_filter: Optional[JobStatusEnum] = Field(None, alias="status", description="Filter jobs by their status (e.g., PENDING, COMPLETED)."),
    db: Session = Depends(get_db_session)
):
    """
    List all processing jobs, optionally filtered by status.
    """
    query = db.query(JobModel).order_by(JobModel.created_at.desc())

    if status_filter:
        # Convert Pydantic Enum to ORM Enum for filtering
        orm_status = JobModelStatus(status_filter.value)
        query = query.filter(JobModel.status == orm_status)

    jobs = query.all()

    return [JobResponse.from_orm(job) for job in jobs]

@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel a running or pending job",
    description="Attempt to cancel a job. The job's status will be updated to CANCELED if successful. Note: This sends a cancellation signal; actual termination depends on the processing core's implementation."
)
async def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db_session)
):
    """
    Cancel a running or pending job by its ID.
    """
    job = db.query(JobModel).filter(JobModel.job_id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )

    # Convert ORM status to Pydantic Enum for comparison
    current_status = JobStatusEnum(job.status.value)
    if current_status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.CANCELED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} cannot be canceled as it is already in '{current_status.value}' state."
        )

    # Update job status in DB to CANCELED
    job.status = JobModelStatus.CANCELED # Use ORM's Enum
    job.updated_at = datetime.utcnow()
    job.error_message = "Job canceled by user request." # Optional: Add a message
    db.add(job)
    db.commit()
    db.refresh(job)

    # In a real system, you might also send a signal to the running processor
    # to actually stop the work. For this API definition, we primarily handle the DB state.
    # The `process_job_request` in core/processor would need to handle this signal.

    return JobResponse.from_orm(job)