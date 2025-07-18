import logging
from typing import Dict, Any, Optional

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from karyaksham_api.core.config import settings
from karyaksham_api.db.session import get_db
from karyaksham_api.crud.crud_job import CRUDJob
from karyaksham_api.schemas.job import JobStatus, JobProcessingParams
from karyaksham_workers.celery_app import celery_app

# Set up logging for this module
logger = logging.getLogger(__name__)
# Ensure logger level is configured via settings
logger.setLevel(settings.LOG_LEVEL)

# Import the Rust engine module
# This import assumes that `maturin` builds the rust_engine crate into a Python wheel
# that gets installed into the Python environment, making `rust_engine` importable.
try:
    import rust_engine
    logger.info("Successfully loaded Rust engine module.")
except ImportError:
    # This should ideally lead to container startup failure in production,
    # as the core processing engine is missing. For local dev/testing,
    # it might be useful to log and continue, but processing tasks will fail.
    logger.critical("Rust engine module 'rust_engine' not found. "
                    "Ensure it's built and installed as a Python package. "
                    "Processing tasks will fail without it.", exc_info=True)
    rust_engine = None # Mark as None to prevent AttributeError later


# Initialize CRUD operations for jobs outside the task for reusability
crud_job = CRUDJob()

# Define a custom exception for task failures that should trigger a retry
class ProcessingTaskTransientError(Exception):
    """
    Custom exception for transient errors in processing tasks that should be retried.
    Examples: database connection issues, temporary object storage unavailability.
    """
    pass

@celery_app.task(
    bind=True,  # Allows the task to access itself (self)
    default_retry_delay=settings.CELERY_RETRY_DELAY_SECONDS,  # Configurable delay
    max_retries=settings.CELERY_MAX_RETRIES,  # Configurable max retries
    acks_late=True,  # Task is acknowledged after it's complete, not just received
    # If the worker crashes, the message goes back to the queue
    # Potentially increase visibility timeout for long-running tasks for SQS/Redis brokers
    # Time limits should be set in Celery configuration if needed (soft_time_limit, time_limit)
)
def process_file_task(self, job_id: int, user_id: int) -> Dict[str, Any]:
    """
    Celery task to orchestrate file processing using the Rust engine.

    This task performs the following steps:
    1. Fetches job details from the database.
    2. Performs basic ownership validation.
    3. Updates job status to RUNNING.
    4. Invokes the high-performance Rust engine to process the file, streaming directly
       from and to object storage.
    5. Updates job status to COMPLETED or FAILED based on processing outcome.
    6. Handles transient errors by retrying the task.

    Args:
        job_id (int): The ID of the job to process.
        user_id (int): The ID of the user who initiated the job, for security/tenancy checks.

    Returns:
        Dict[str, Any]: A dictionary containing the job_id and final status.
    """
    db: Optional[Session] = None
    job = None
    error_message: Optional[str] = None
    final_status: JobStatus = JobStatus.FAILED

    try:
        # Establish a new database session for this task execution
        db = next(get_db())

        # Retrieve job details from the database
        job = crud_job.get(db, job_id)
        if not job:
            error_message = f"Job with ID {job_id} not found."
            logger.error(error_message)
            return {"job_id": job_id, "status": JobStatus.FAILED.value, "error": error_message}

        # Basic security check: Ensure the job belongs to the user
        if job.owner_id != user_id:
            error_message = (f"Unauthorized access attempt: User {user_id} attempted to process job {job_id} "
                             f"owned by {job.owner_id}. This incident will be logged.")
            logger.warning(error_message) # Warning instead of error for this case
            crud_job.update_status(db, job_id, JobStatus.FAILED, error_message=error_message)
            db.commit() # Ensure status update is persisted
            return {"job_id": job_id, "status": JobStatus.FAILED.value, "error": "Unauthorized access"}

        # Check if job is already in a final state to prevent re-processing
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            logger.info(f"Job {job_id} is already in state {job.status.value}. Skipping processing.")
            return {"job_id": job_id, "status": job.status.value}

        logger.info(f"Starting processing for Job ID: {job_id} (Input: {job.input_file_path})")

        # Update job status to RUNNING and commit immediately
        crud_job.update_status(db, job_id, JobStatus.RUNNING)
        db.commit()

        # Ensure Rust engine is loaded before attempting to call it
        if rust_engine is None:
            raise RuntimeError("Rust engine is not loaded. Cannot perform processing.")

        # Parse processing parameters from the job model
        # The `job.processing_params_json` field is expected to be a dictionary
        # derived from a JSONB column in PostgreSQL.
        processing_params_dict = job.processing_params_json if job.processing_params_json else {}
        
        # Validate processing_params_dict using the Pydantic schema for robustness
        try:
            processing_config = JobProcessingParams(**processing_params_dict)
        except Exception as e:
            raise ValueError(f"Invalid processing parameters for job {job_id}: {e}")

        # Determine output file path based on input path and desired output format
        # This is a simplified example. A more robust solution might involve:
        # 1. Generating a unique path (e.g., using job_id or UUID).
        # 2. Storing output in a job-specific subfolder in object storage.
        # The output format is determined by `processing_config.output_format`.
        input_file_path = job.input_file_path
        
        # Example output path generation: s3://bucket/user_id/input_file_name.csv -> s3://bucket/user_id/output_job_id.parquet
        # A more robust path could be `settings.OBJECT_STORAGE_BUCKET/jobs/{job_id}/output.{output_format}`
        # For simplicity, let's derive it from the input path, ensuring unique job-specific output.
        # This might need a more centralized utility function in the future.
        
        # Let's use a job-specific path within the user's "folder"
        path_parts = input_file_path.split('/')
        bucket_prefix = "/".join(path_parts[:3]) # e.g., s3://my_bucket
        key_prefix = "/".join(path_parts[3:-1]) # e.g., user_123
        original_filename = path_parts[-1].rsplit('.', 1)[0]
        
        output_format = processing_config.output_format.value if processing_config.output_format else "parquet"
        output_key = f"{key_prefix}/{original_filename}_job_{job_id}.{output_format}"
        output_file_path = f"{bucket_prefix}/{output_key}"

        # Call the Rust engine function to perform the actual data processing
        # The Rust function is expected to handle streaming data directly
        # from the `input_file_path` and writing to `output_file_path` in object storage.
        # It also takes the `processing_params_dict` which the Rust side will parse
        # based on its internal logic (e.g., using Serde).
        logger.debug(f"Calling rust_engine.process_data with: "
                     f"input='{input_file_path}', output='{output_file_path}', "
                     f"params={processing_params_dict}")

        rust_engine.process_data(
            input_file_path=input_file_path,
            output_file_path=output_file_path,
            processing_config=processing_params_dict # Pass dictionary directly
        )

        # If Rust processing completes without error, update job status to COMPLETED
        crud_job.update_status(db, job_id, JobStatus.COMPLETED, output_file_path=output_file_path)
        db.commit() # Commit final status update
        final_status = JobStatus.COMPLETED
        logger.info(f"Successfully processed Job ID: {job_id}. Output: {output_file_path}")

        return {"job_id": job_id, "status": final_status.value, "output_path": output_file_path}

    except (OperationalError, SQLAlchemyError) as exc:
        # Catch database-related errors as transient and trigger a retry
        error_message = f"Database error during processing for Job ID {job_id}: {type(exc).__name__} - {exc}"
        logger.error(error_message, exc_info=True)
        # Mark as transient, allowing Celery to retry
        raise ProcessingTaskTransientError(error_message) from exc

    except ProcessingTaskTransientError as exc:
        # This block catches `ProcessingTaskTransientError` raised either here or from
        # a wrapped lower-level exception.
        logger.warning(f"Transient error for Job ID {job_id}: {exc}. Attempting retry {self.request.retries + 1}/{self.max_retries}...")
        try:
            # Re-raise with retry
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            # If max retries are exceeded, log and mark job as FAILED
            error_message = f"Max retries exceeded for Job ID {job_id} due to transient error: {exc}"
            logger.error(error_message)
            if db and job: # Ensure db and job objects are available before attempting update
                crud_job.update_status(db, job_id, JobStatus.FAILED, error_message=error_message)
                db.commit()
            return {"job_id": job_id, "status": JobStatus.FAILED.value, "error": error_message}

    except Exception as exc:
        # Catch any other unexpected exceptions during processing
        error_message = f"Processing failed for Job ID {job_id}: {type(exc).__name__} - {exc}"
        logger.exception(error_message) # Log with traceback

        if db and job: # Ensure db and job objects are available before attempting update
            # Attempt to update job status to FAILED
            crud_job.update_status(db, job_id, JobStatus.FAILED, error_message=error_message)
            db.commit() # Commit status update
        elif db: # If job object could not be fetched
             # Log that the job could not be updated in DB, but db session exists
            logger.error(f"Could not update status for Job ID {job_id} in DB after failure due to job object not found or initial error. Error: {error_message}")
        
        return {"job_id": job_id, "status": JobStatus.FAILED.value, "error": error_message}

    finally:
        # Ensure database session is closed regardless of success or failure
        if db:
            db.close()
            logger.debug(f"Database session closed for Job ID: {job_id}")