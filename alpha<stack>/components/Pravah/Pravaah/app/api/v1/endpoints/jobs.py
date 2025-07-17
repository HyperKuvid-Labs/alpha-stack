import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1 import schemas
from app.api.v1.dependencies import get_db
from app.core.jobs import JobManager  # Manages job creation, retrieval, updates
from app.db.models.job import JobStatus  # Enum for job statuses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "/",
    response_model=schemas.Job,
    status_code=status.HTTP_201_CREATED,
    summary="Create and start a new data processing job",
    description="Submits a request to process files based on the provided input and output paths, and processing configurations. The job is initially set to PENDING and will be picked up by a worker. Returns the newly created job details."
)
async def create_job(
    job_create_data: schemas.JobCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new job in the system. The job will be assigned a unique ID,
    and its initial status will be `PENDING`.

    Args:
        job_create_data (schemas.JobCreate): The details for the new job,
                                            including name, input_path, output_path,
                                            and optional processing configurations.
        db (Session): Database session dependency.

    Returns:
        schemas.Job: The newly created job object with its assigned ID and initial status.

    Raises:
        HTTPException: If there's an internal server error during job creation.
    """
    logger.info(f"Received request to create job: {job_create_data.name}")
    job_manager = JobManager(db)
    try:
        db_job = await job_manager.create_job(job_create_data)
        logger.info(f"Job {db_job.id} created successfully.")
        return db_job
    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {e}"
        )


@router.get(
    "/{job_id}",
    response_model=schemas.Job,
    summary="Retrieve the status and details of a specific job",
    description="Fetches comprehensive information about a data processing job, including its current status, input/output paths, and timestamps."
)
async def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves the current status and detailed information for a specific job by its ID.

    Args:
        job_id (UUID): The unique identifier of the job.
        db (Session): Database session dependency.

    Returns:
        schemas.Job: The job object containing its current state.

    Raises:
        HTTPException: If the job with the given ID is not found.
    """
    logger.info(f"Received request to get status for job ID: {job_id}")
    job_manager = JobManager(db)
    db_job = await job_manager.get_job(job_id)
    if not db_job:
        logger.warning(f"Job with ID {job_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    logger.debug(f"Returning details for job {job_id}.")
    return db_job


@router.get(
    "/{job_id}/results",
    response_model=schemas.Job,  # Assuming results_url is part of the Job schema
    summary="Retrieve the results of a completed job",
    description="If a job has successfully completed, this endpoint provides access to its results, which might include a URL to the output location or summary data."
)
async def get_job_results(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves the results of a completed job. If the job is still running or has failed,
    an appropriate error will be returned.

    Args:
        job_id (UUID): The unique identifier of the job.
        db (Session): Database session dependency.

    Returns:
        schemas.Job: The job object, including the `results_url` if available.

    Raises:
        HTTPException:
            - If the job with the given ID is not found.
            - If the job has not yet completed (status is not `COMPLETED`).
            - If the job completed but no results URL was recorded.
    """
    logger.info(f"Received request to get results for job ID: {job_id}")
    job_manager = JobManager(db)
    db_job = await job_manager.get_job(job_id)

    if not db_job:
        logger.warning(f"Job with ID {job_id} not found when requesting results.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )

    if db_job.status != JobStatus.COMPLETED:
        logger.warning(f"Job {job_id} is not completed. Current status: {db_job.status.value}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is not yet completed. Current status: {db_job.status.value}. Please check back later."
        )

    if not db_job.results_url:
        logger.warning(f"Job {job_id} completed but no results_url found.")
        # This scenario should ideally be prevented or clearly indicate no direct results via URL.
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,  # Or 404/500 if a URL is strictly expected
            detail=f"Job {job_id} completed but no direct results URL available. Results might be implicitly stored or require a different retrieval method."
        )

    logger.debug(f"Returning results for job {job_id}.")
    return db_job


@router.get(
    "/",
    response_model=List[schemas.Job],
    summary="List all data processing jobs",
    description="Retrieves a list of all data processing jobs, with optional filtering by status and pagination."
)
async def list_jobs(
    db: Session = Depends(get_db),
    status_filter: JobStatus | None = None,  # Query parameter for filtering by status
    limit: int = 100,
    offset: int = 0
):
    """
    Lists all jobs available in the system. Can be filtered by their current status
    and supports pagination to handle large numbers of jobs.

    Args:
        db (Session): Database session dependency.
        status_filter (JobStatus | None): Optional. Filter jobs by this status.
        limit (int): The maximum number of jobs to return. Defaults to 100.
        offset (int): The number of jobs to skip before starting to return results. Defaults to 0.

    Returns:
        List[schemas.Job]: A list of job objects matching the criteria.
    """
    logger.info(f"Received request to list jobs. Status filter: {status_filter}, Limit: {limit}, Offset: {offset}")
    job_manager = JobManager(db)
    jobs = await job_manager.list_jobs(status=status_filter, limit=limit, offset=offset)
    logger.debug(f"Returning {len(jobs)} jobs.")
    return jobs