import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.job import Job, JobStatus
from app.api.schemas import JobCreate, JobResponse, JobResult
from app.core.processor import process_files_with_rust
from app.utils.logging import logger

class JobService:
    """
    Manages the lifecycle of processing jobs, including creation, status tracking,
    and orchestration of the underlying Rust-based file processing.
    """
    def __init__(self, db_session_factory: Callable[..., AsyncSession]):
        """
        Initializes the JobService with a factory for creating database sessions.
        This factory is crucial for allowing background tasks to create their
        own session context.
        """
        self._db_session_factory = db_session_factory

    async def create_job(self, job_data: JobCreate) -> JobResponse:
        """
        Creates a new job record in the database and asynchronously initiates its processing.

        Args:
            job_data (JobCreate): Pydantic model containing job input parameters.

        Returns:
            JobResponse: Pydantic model representing the newly created job,
                         with its initial PENDING status.
        """
        async with self._db_session_factory() as db:
            job_id = uuid.uuid4()
            new_job = Job(
                id=job_id,
                status=JobStatus.PENDING,
                input_path=job_data.input_path,
                output_path=job_data.output_path,
                processing_config=job_data.processing_config,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(new_job)
            await db.commit()
            await db.refresh(new_job) # Refresh to get any database-generated defaults or relationships

            logger.info(f"Job {job_id} created with status '{JobStatus.PENDING.value}'. Initiating background processing...")

            # Initiate background processing without blocking the API response.
            # asyncio.create_task ensures the processing runs concurrently.
            asyncio.create_task(
                self._run_job_processing(
                    job_id=job_id,
                    input_path=job_data.input_path,
                    output_path=job_data.output_path,
                    processing_config=job_data.processing_config
                )
            )

            return JobResponse.from_orm(new_job)

    async def get_job_by_id(self, job_id: uuid.UUID) -> Optional[JobResponse]:
        """
        Retrieves a job's details by its unique identifier.

        Args:
            job_id (uuid.UUID): The UUID of the job to retrieve.

        Returns:
            Optional[JobResponse]: The job details if found, otherwise None.
        """
        async with self._db_session_factory() as db:
            result = await db.execute(select(Job).filter(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                return JobResponse.from_orm(job)
            logger.info(f"Job {job_id} not found.")
            return None

    async def _update_job_status(self, db: AsyncSession, job_id: uuid.UUID, status: JobStatus,
                                  result_details: Optional[Dict[str, Any]] = None):
        """
        Internal helper to update a job's status and optionally its result details in the database.

        Args:
            db (AsyncSession): The SQLAlchemy asynchronous database session.
            job_id (uuid.UUID): The UUID of the job to update.
            status (JobStatus): The new status for the job.
            result_details (Optional[Dict[str, Any]]): Optional dictionary containing
                                                       details of the job's outcome.
        """
        result = await db.execute(select(Job).filter(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            job.updated_at = datetime.utcnow()
            if result_details is not None:
                job.result_details = result_details
            await db.commit()
            await db.refresh(job) # Refresh to ensure job object reflects committed state
            logger.info(f"Job {job_id} status updated to '{status.value}'.")
        else:
            logger.warning(f"Could not find job {job_id} to update status. It might have been deleted or an invalid ID was provided.")


    async def _run_job_processing(self, job_id: uuid.UUID, input_path: str, output_path: str,
                                   processing_config: Dict[str, Any]):
        """
        The core logic for processing a job. This function runs as an asynchronous
        background task. It updates the job status, calls the Rust processing engine,
        and records the final outcome (success or failure).

        Args:
            job_id (uuid.UUID): The UUID of the job being processed.
            input_path (str): The input path for the processing job.
            output_path (str): The output path for the processed results.
            processing_config (Dict[str, Any]): Configuration options for the processing.
        """
        async with self._db_session_factory() as db:
            try:
                # Update job status to RUNNING
                await self._update_job_status(db, job_id, JobStatus.RUNNING)
                logger.info(f"Job {job_id} commenced processing with Rust engine.")

                # Call the Rust-backed processing function.
                # This function is expected to return a dictionary of results
                # on success or raise an exception on failure.
                raw_processing_result: Dict[str, Any] = await process_files_with_rust(
                    job_id=str(job_id), # Pass UUID as string for Rust interoperability
                    input_path=input_path,
                    output_path=output_path,
                    processing_config=processing_config,
                )

                # Validate and parse the raw result into a Pydantic model
                job_result = JobResult(**raw_processing_result)

                # Update job status to COMPLETED and store the structured results
                await self._update_job_status(db, job_id, JobStatus.COMPLETED, job_result.dict())
                logger.info(f"Job {job_id} completed successfully. Files processed: {job_result.files_processed}.")

            except Exception as e:
                # Handle any exceptions during processing and update job status to FAILED
                error_details = {
                    "error_message": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "traceback": "See application logs for detailed traceback." # Avoid storing full traceback in DB for brevity
                }
                logger.error(f"Job {job_id} failed during processing: {e}", exc_info=True)
                await self._update_job_status(db, job_id, JobStatus.FAILED, error_details)
            finally:
                # Ensure the database session is closed even if there's an unhandled exception
                await db.close()