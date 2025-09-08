import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

# Local imports
from ..core.job_manager import JobManager
from ..database.connection import get_db_session
# Assuming sanchay_app.database.models.py defines a Job model and a JobStatus Enum
from ..database.models import Job as DBJobModel, JobStatus as DBJobStatus


# --- Pydantic Models for API ---

class JobType(str, Enum):
    """Enumeration of supported job types."""
    CHECKSUM = "checksum"
    DUPLICATE_CHECK = "duplicate_check"
    METADATA_EXTRACT = "metadata_extract"
    # Extend with other job types as they are implemented in sanchay_core


class StartJobRequest(BaseModel):
    """Request body for starting a new processing job."""
    path: str = Field(..., description="The root path for the processing job (local filesystem path or S3 URI).")
    job_type: JobType = Field(..., description="The type of processing job to perform.")
    recursive: bool = Field(True, description="Whether to process directories recursively.")
    # Future: Add other job-specific parameters if needed, e.g., 'filters', 'settings'
    # settings: Optional[Dict[str, Any]] = Field(None, description="Optional job-specific settings.")


class JobResponse(BaseModel):
    """Response model for a processing job's status."""
    job_id: str = Field(..., description="Unique identifier for the job.")
    path: str = Field(..., description="The root path being processed by the job.")
    job_type: JobType = Field(..., description="The type of processing job performed.")
    status: str = Field(..., description="Current status of the job (e.g., PENDING, RUNNING, COMPLETED, FAILED).")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress of the job (0.0 to 1.0).")
    message: Optional[str] = Field(None, description="An optional message about the job's current state or error.")
    start_time: datetime = Field(..., description="Timestamp when the job was started.")
    end_time: Optional[datetime] = Field(None, description="Timestamp when the job was completed or failed.")
    results_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of the job results (e.g., files processed, duplicates found).")
    error_detail: Optional[str] = Field(None, description="Detailed error message if the job failed.")


# --- Dependencies ---

def get_job_manager(db_session: Any = Depends(get_db_session)) -> JobManager:
    """
    Dependency to provide a JobManager instance.
    It injects a database session, allowing JobManager to interact with the database
    to persist and retrieve job states.
    """
    return JobManager(db_session)


# --- API Router ---

router = APIRouter(
    prefix="/jobs",
    tags=["Job Management"],
    responses={404: {"description": "Job not found"}},
)


# --- API Endpoints ---

@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new file processing job",
    description="Initiates a new background job to process files in a specified directory or storage path. "
                "The job runs asynchronously, and its status can be monitored via other endpoints."
)
async def start_new_job(
    request: StartJobRequest,
    job_manager: JobManager = Depends(get_job_manager)
) -> JobResponse:
    """
    Starts a new asynchronous file processing job.

    - **path**: The target directory or cloud storage URI to scan.
    - **job_type**: The type of processing to perform (e.g., 'checksum', 'duplicate_check').
    - **recursive**: A boolean indicating whether to scan subdirectories.
    """
    try:
        # JobManager.start_job is expected to create a DB entry for the job
        # and then initiate the actual processing in a non-blocking way
        job_id = await job_manager.start_job(
            path=request.path,
            job_type=request.job_type.value, # Pass enum value as string to manager
            recursive=request.recursive
            # Future: pass request.settings if implemented
        )
        # Fetch the newly created job's status to return the initial state
        job_status: Optional[DBJobModel] = await job_manager.get_job_status(job_id)
        if not job_status:
            # This case should ideally not happen if start_job successfully creates a job
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Job started but could not retrieve its initial status."
            )

        # Convert DB model to Pydantic model for response
        return JobResponse(
            job_id=job_status.job_id,
            path=job_status.path,
            job_type=JobType(job_status.job_type), # Convert DB string back to API Enum
            status=job_status.status.value if isinstance(job_status.status, DBJobStatus) else str(job_status.status),
            progress=job_status.progress,
            message=job_status.message,
            start_time=job_status.start_time,
            end_time=job_status.end_time,
            results_summary=job_status.results_summary,
            error_detail=job_status.error_detail
        )
    except ValueError as e:
        # Catch validation errors or specific business logic errors from JobManager
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Catch any unexpected errors during job initiation
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while starting the job: {e}"
        )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve the status of a specific job",
    description="Fetches the current status, progress, and any results summary for a given job ID."
)
async def get_job_status(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager)
) -> JobResponse:
    """
    Retrieves the status of a specific processing job by its ID.

    - **job_id**: The unique identifier of the job.
    """
    job_status: Optional[DBJobModel] = await job_manager.get_job_status(job_id)
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    # Convert DB model to Pydantic model for response
    return JobResponse(
        job_id=job_status.job_id,
        path=job_status.path,
        job_type=JobType(job_status.job_type),
        status=job_status.status.value if isinstance(job_status.status, DBJobStatus) else str(job_status.status),
        progress=job_status.progress,
        message=job_status.message,
        start_time=job_status.start_time,
        end_time=job_status.end_time,
        results_summary=job_status.results_summary,
        error_detail=job_status.error_detail
    )


@router.get(
    "/",
    response_model=List[JobResponse],
    summary="List all active or recent jobs",
    description="Retrieves a list of all processing jobs, optionally filtered by their status."
)
async def list_jobs(
    status_filter: Optional[str] = Field(None, description="Optional. Filter jobs by their status (e.g., 'RUNNING', 'COMPLETED', 'FAILED')."),
    job_manager: JobManager = Depends(get_job_manager)
) -> List[JobResponse]:
    """
    Lists all active or recent processing jobs.

    - **status_filter**: An optional query parameter to filter jobs by their current status.
    """
    jobs: List[DBJobModel] = await job_manager.list_jobs(status_filter=status_filter)

    # Return an empty list if no jobs are found or matched the filter
    if not jobs:
        return []

    # Convert list of DB models to list of Pydantic models for response
    return [
        JobResponse(
            job_id=job.job_id,
            path=job.path,
            job_type=JobType(job.job_type),
            status=job.status.value if isinstance(job.status, DBJobStatus) else str(job.status),
            progress=job.progress,
            message=job.message,
            start_time=job.start_time,
            end_time=job.end_time,
            results_summary=job.results_summary,
            error_detail=job.error_detail
        ) for job in jobs
    ]


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel or delete a job",
    description="Attempts to cancel a running job gracefully or deletes a completed/failed job record from the system."
)
async def cancel_or_delete_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Cancels a running job (if possible) or deletes a job record from the database.

    - **job_id**: The ID of the job to cancel or delete.
    """
    try:
        # JobManager.cancel_or_delete_job is expected to handle the logic
        # of either cancelling a running job or deleting a finished job's record.
        success = await job_manager.cancel_or_delete_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID '{job_id}' not found or could not be cancelled/deleted due to its current state."
            )
        # FastAPI automatically returns 204 No Content for functions that don't return a response
    except ValueError as e:
        # Catch specific business logic errors, e.g., trying to cancel a non-cancellable job
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Catch any unexpected errors during cancellation/deletion
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing job '{job_id}': {e}"
        )