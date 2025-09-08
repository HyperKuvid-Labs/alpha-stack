import asyncio
import uuid
import logging
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from sanchay_app.utils.logging_config import setup_logging
from sanchay_app.database.models import Job as DBJob, JobStatus as DBJobStatus, ProcessingResult
from sanchay_app.database.connection import get_session

# Import the Rust core extension. This will fail if the Rust extension hasn't been built
# or is not in the Python path. The manager should still be able to initialize.
try:
    import sanchay_core
except ImportError:
    logging.getLogger(__name__).warning(
        "sanchay_core Rust extension not found. Some functionality (job execution) will be limited."
    )
    sanchay_core = None # Set to None and handle gracefully

logger = setup_logging(__name__)

class JobStatus(Enum):
    """Enumeration for the various states of a processing job."""
    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()    # Future use: to allow pausing ongoing jobs
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

class JobProgress:
    """Represents the current progress of a processing job."""
    def __init__(self,
                 total_items: int = 0,
                 processed_items: int = 0,
                 current_item_name: str = "",
                 items_per_second: float = 0.0,
                 eta_seconds: Optional[int] = None,
                 message: str = "Initializing...",
                 error: Optional[str] = None):
        self.total_items = total_items
        self.processed_items = processed_items
        self.current_item_name = current_item_name
        self.items_per_second = items_per_second
        self.eta_seconds = eta_seconds
        self.message = message
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Converts the JobProgress object to a dictionary."""
        return {
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "current_item_name": self.current_item_name,
            "items_per_second": self.items_per_second,
            "eta_seconds": self.eta_seconds,
            "message": self.message,
            "error": self.error
        }

class ActiveJob:
    """Internal representation of an actively running job, linking DB model, task, and progress."""
    def __init__(self, db_job: DBJob, task: asyncio.Task, progress_queue: asyncio.Queue):
        self.db_job = db_job
        self.task = task
        self.progress_queue = progress_queue
        self.latest_progress = JobProgress() # Stores the most recent progress report

    @property
    def id(self) -> uuid.UUID:
        return self.db_job.id

    @property
    def status(self) -> JobStatus:
        return JobStatus[self.db_job.status.name]

    def update_progress(self, progress: JobProgress):
        """Updates the stored latest progress."""
        self.latest_progress = progress

class JobManager:
    """
    Manages the lifecycle, execution, and state of file processing jobs.
    Orchestrates calls to the Rust core and updates the database.
    Implemented as an asynchronous singleton.
    """
    _instance: Optional['JobManager'] = None
    _lock: asyncio.Lock = asyncio.Lock() # For async singleton initialization

    def __new__(cls):
        """Ensures only one instance of JobManager is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def __ainit__(self):
        """
        Asynchronous initialization method. Must be called after `__new__`
        for the singleton instance.
        """
        if not hasattr(self, '_initialized'):
            self.active_jobs: Dict[uuid.UUID, ActiveJob] = {}
            self.logger = logger
            self._initialized = True
            self.logger.info("JobManager initialized.")

    @classmethod
    async def get_instance(cls) -> 'JobManager':
        """
        Provides an asynchronous, thread-safe way to get the singleton instance.
        Ensures `__ainit__` is called exactly once.
        """
        async with cls._lock:
            if cls._instance is None:
                instance = cls() # Calls __new__
                await instance.__ainit__()
            elif not hasattr(cls._instance, '_initialized'):
                # In case __new__ was called, but __ainit__ hasn't completed yet
                await cls._instance.__ainit__()
            return cls._instance

    async def create_job(self, job_type: str, target_path: str, parameters: Optional[Dict[str, Any]] = None) -> DBJob:
        """
        Creates a new job record in the database with PENDING status.
        Returns the created DBJob object.
        """
        async with get_session() as session:
            new_db_job = DBJob(
                id=uuid.uuid4(),
                job_type=job_type,
                target_path=target_path,
                parameters=parameters or {},
                status=DBJobStatus.PENDING,
                created_at=datetime.utcnow()
            )
            session.add(new_db_job)
            await session.commit()
            await session.refresh(new_db_job) # Refresh to get any DB-assigned defaults/timestamps
            self.logger.info(f"Job created: ID={new_db_job.id}, Type={job_type}, Path={target_path}")
            return new_db_job

    async def start_job(self, job_id: uuid.UUID):
        """
        Starts the execution of a previously created job.
        Raises ValueError if job not found or cannot be started.
        """
        async with get_session() as session:
            db_job = await session.execute(
                select(DBJob).filter_by(id=job_id)
            ).scalar_one_or_none()

            if not db_job:
                self.logger.error(f"Attempted to start non-existent job: {job_id}")
                raise ValueError(f"Job with ID {job_id} not found.")

            if db_job.status == DBJobStatus.RUNNING:
                self.logger.warning(f"Job {job_id} is already RUNNING. Not starting again.")
                return
            
            if db_job.status not in (DBJobStatus.PENDING, DBJobStatus.FAILED, DBJobStatus.CANCELLED):
                self.logger.warning(f"Job {job_id} is in status {db_job.status.name}. Can only start PENDING, FAILED, or CANCELLED jobs.")
                return

            db_job.status = DBJobStatus.RUNNING
            db_job.started_at = datetime.utcnow()
            session.add(db_job)
            await session.commit()
            await session.refresh(db_job)

            # Create an asyncio.Queue for Rust to push progress updates into
            progress_queue = asyncio.Queue()
            task = asyncio.create_task(
                self._run_processing_task(db_job, progress_queue),
                name=f"job_task_{job_id}"
            )
            self.active_jobs[job_id] = ActiveJob(db_job, task, progress_queue)
            self.logger.info(f"Job {job_id} started. Type: {db_job.job_type}")

    async def cancel_job(self, job_id: uuid.UUID):
        """
        Requests cancellation of an active job.
        If the job is not active but was running, it attempts to update its DB status.
        """
        job = self.active_jobs.get(job_id)
        if job:
            if job.task.done():
                self.logger.info(f"Job {job_id} is already finished (status: {job.db_job.status.name}), cannot cancel.")
                return

            self.logger.info(f"Attempting to cancel job: {job_id}")
            job.task.cancel() # Request cancellation
            try:
                await job.task # Await the task to truly finish (or raise CancelledError)
                self.logger.info(f"Job {job_id} successfully cancelled.")
            except asyncio.CancelledError:
                self.logger.info(f"Job {job_id} cancellation acknowledged and handled.")
            except Exception as e:
                self.logger.error(f"Error during cancellation of job {job_id}: {e}", exc_info=True)
            finally:
                await self._update_job_status(job.id, JobStatus.CANCELLED, error_message="User cancelled job.")
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id] # Remove from active jobs after processing cancellation
        else:
            self.logger.warning(f"Job {job_id} not found among active jobs. Checking DB status.")
            # If not in active_jobs, check if it was running and update in DB
            async with get_session() as session:
                db_job = await session.execute(
                    select(DBJob).filter_by(id=job_id)
                ).scalar_one_or_none()
                if db_job and db_job.status == DBJobStatus.RUNNING:
                    await self._update_job_status(job_id, JobStatus.CANCELLED, error_message="Job was active but not tracked by JobManager (possible restart issue).")
                else:
                    self.logger.info(f"Job {job_id} found in DB (status: {db_job.status.name if db_job else 'N/A'}), but not running or cannot be cancelled.")


    async def get_job_info(self, job_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Returns comprehensive information about a job, including its latest progress
        if it's an active job.
        """
        async with get_session() as session:
            db_job = await session.execute(
                select(DBJob).filter_by(id=job_id)
            ).scalar_one_or_none()

            if not db_job:
                return None

            job_data = {
                "id": str(db_job.id),
                "job_type": db_job.job_type,
                "target_path": db_job.target_path,
                "status": db_job.status.name,
                "created_at": db_job.created_at.isoformat() if db_job.created_at else None,
                "started_at": db_job.started_at.isoformat() if db_job.started_at else None,
                "completed_at": db_job.completed_at.isoformat() if db_job.completed_at else None,
                "total_items_processed": db_job.total_items_processed,
                "error_message": db_job.error_message,
                "parameters": db_job.parameters
            }

            active_job = self.active_jobs.get(job_id)
            if active_job:
                # Provide real-time progress for active jobs
                job_data["progress"] = active_job.latest_progress.to_dict()
            else:
                # For inactive jobs, synthesize a "final" progress report based on DB data
                job_data["progress"] = JobProgress(
                    total_items=db_job.total_items_processed,
                    processed_items=db_job.total_items_processed,
                    message=f"{db_job.status.name}." if db_job.error_message is None else db_job.error_message,
                    error=db_job.error_message
                ).to_dict()

            return job_data

    async def list_jobs(self) -> list[Dict[str, Any]]:
        """
        Lists all jobs (active and inactive) from the database with their current status
        and latest available progress information.
        """
        async with get_session() as session:
            stmt = select(DBJob).order_by(DBJob.created_at.desc())
            db_jobs = (await session.execute(stmt)).scalars().all()

            job_list = []
            for db_job in db_jobs:
                job_info = await self.get_job_info(db_job.id)
                if job_info:
                    job_list.append(job_info)
            return job_list


    async def _run_processing_task(self, db_job: DBJob, progress_queue: asyncio.Queue):
        """
        Internal method to execute the actual processing logic, calling the Rust core.
        Listens for progress updates from the Rust core via the provided progress_queue.
        This runs as an asyncio.Task.
        """
        job_id = db_job.id
        job_type = db_job.job_type
        target_path = db_job.target_path
        job_parameters = db_job.parameters

        current_job_progress = JobProgress()
        final_rust_results: Optional[Any] = None # To store the final return value from the Rust call

        try:
            if sanchay_core is None:
                raise RuntimeError("Rust core (sanchay_core) not loaded. Cannot run processing task.")

            rust_func = None
            if job_type == "scan_directory":
                rust_func = getattr(sanchay_core, 'scan_directory_py', None)
            elif job_type == "find_duplicates":
                rust_func = getattr(sanchay_core, 'find_duplicates_py', None)
            # Add more job types as needed

            if rust_func is None:
                raise AttributeError(f"Rust core does not have the required function for job type '{job_type}'.")

            self.logger.info(f"Calling Rust core for {job_type} job {job_id} on path: {target_path}")

            # Run the synchronous Rust function in a separate thread to avoid blocking the event loop.
            # The Rust function is expected to take (path: str, progress_queue_obj: PyAny)
            # and put dicts matching JobProgress structure (or special markers) into the queue.
            rust_task_future = asyncio.to_thread(
                rust_func, target_path, progress_queue # progress_queue is a PyAny from Rust's perspective
            )

            # Continuously monitor the progress queue while the Rust task is running
            while True:
                # Use asyncio.wait with a timeout to allow checking for both progress updates
                # and the completion of the Rust task.
                try:
                    # Wait for either a new item in the progress queue, or the Rust task to complete
                    done, pending = await asyncio.wait(
                        [rust_task_future, progress_queue.get()],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=0.2 # Small timeout to periodically check on the Rust future
                    )

                    if progress_queue.get() in done:
                        # A progress update or a special message has arrived
                        progress_data = progress_queue.get_nowait()
                        
                        if progress_data == "__SANCHAY_JOB_COMPLETE__":
                            self.logger.debug(f"Job {job_id} received 'JOB_COMPLETE' signal from Rust.")
                            # The Rust task might still be in 'pending' if it put this then quickly returned
                            # or if there's a race. We'll break once rust_task_future is also done.
                            break 
                        elif progress_data == "__SANCHAY_JOB_ERROR__":
                            self.logger.error(f"Job {job_id} received 'JOB_ERROR' signal from Rust.")
                            raise RuntimeError("Rust core reported an error during processing.")
                        else:
                            # Assume Rust sends dicts directly convertible to JobProgress
                            current_job_progress = JobProgress(**progress_data)
                            if job_id in self.active_jobs:
                                self.active_jobs[job_id].update_progress(current_job_progress)
                            self.logger.debug(
                                f"Job {job_id} progress: {current_job_progress.processed_items}/"
                                f"{current_job_progress.total_items} ({current_job_progress.message})"
                            )
                    
                    if rust_task_future in done:
                        # The Rust function has completed its execution.
                        final_rust_results = await rust_task_future
                        self.logger.info(f"Rust core task for job {job_id} finished. Result type: {type(final_rust_results)}")
                        # Ensure any remaining progress updates are processed before breaking the loop.
                        # This handles cases where Rust pushes final updates just before returning.
                        while not progress_queue.empty():
                            progress_data = progress_queue.get_nowait()
                            if progress_data == "__SANCHAY_JOB_COMPLETE__":
                                self.logger.debug(f"Job {job_id} processed final 'JOB_COMPLETE' from queue.")
                                break
                            if progress_data == "__SANCHAY_JOB_ERROR__":
                                self.logger.error(f"Job {job_id} processed final 'JOB_ERROR' from queue.")
                                raise RuntimeError("Rust core reported an error during processing.")
                            current_job_progress = JobProgress(**progress_data)
                            if job_id in self.active_jobs:
                                self.active_jobs[job_id].update_progress(current_job_progress)
                        break # Exit the loop, task is definitely done.

                except asyncio.TimeoutError:
                    # No new progress or task completion, just continue looping and checking
                    pass
                except asyncio.CancelledError:
                    self.logger.info(f"Job {job_id} processing task was externally cancelled.")
                    raise # Re-raise to be caught by the outer try-except and update status
                except Exception as e:
                    self.logger.error(f"Error while monitoring job {job_id} progress queue: {e}", exc_info=True)
                    raise # Re-raise to update job status to FAILED

            # If we broke out of the loop, the task is complete.
            # Store final results and update job status.
            if final_rust_results is not None:
                await self._store_processing_results(job_id, final_rust_results)
            
            # Ensure final progress reflects what was processed
            final_processed_items = current_job_progress.processed_items
            if db_job.job_type == "scan_directory" and isinstance(final_rust_results, dict) and "file_count" in final_rust_results:
                 # If scan_directory, the final_rust_results might have the accurate total.
                 final_processed_items = final_rust_results["file_count"]

            await self._update_job_status(job_id, JobStatus.COMPLETED,
                                          total_items_processed=final_processed_items)

        except asyncio.CancelledError:
            self.logger.info(f"Job {job_id} was cancelled before completion.")
            await self._update_job_status(job_id, JobStatus.CANCELLED, error_message="Job cancelled by user.")
        except Exception as e:
            self.logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            await self._update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
        finally:
            # Clean up active job entry regardless of outcome
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            self.logger.info(f"Job {job_id} processing task concluded (status updated in DB).")


    async def _update_job_status(self, job_id: uuid.UUID, status: JobStatus,
                                 total_items_processed: Optional[int] = None,
                                 error_message: Optional[str] = None):
        """
        Updates the status of a job in the database.
        """
        async with get_session() as session:
            db_job = await session.execute(
                select(DBJob).filter_by(id=job_id)
            ).scalar_one_or_none()

            if db_job:
                db_job.status = DBJobStatus[status.name]
                if total_items_processed is not None:
                    db_job.total_items_processed = total_items_processed
                if error_message:
                    db_job.error_message = error_message
                if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    db_job.completed_at = datetime.utcnow()
                session.add(db_job)
                await session.commit()
                self.logger.info(f"Job {job_id} database status updated to {status.name}.")
            else:
                self.logger.warning(f"Could not find job {job_id} in DB to update its status to {status.name}.")

    async def _store_processing_results(self, job_id: uuid.UUID, results: Any):
        """
        Stores the final results of a processing job in the database.
        'results' would be specific to job type (e.g., list of duplicate files, scan summary).
        Assumes `results` can be directly stored as JSON-compatible data.
        """
        if results is None:
            self.logger.debug(f"No results to store for job {job_id}.")
            return

        async with get_session() as session:
            try:
                processing_result = ProcessingResult(
                    job_id=job_id,
                    result_data=results # Requires JSON type in SQLAlchemy model
                )
                session.add(processing_result)
                await session.commit()
                self.logger.info(f"Stored processing results for job {job_id}.")
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Failed to store processing results for job {job_id}: {e}", exc_info=True)

# Example usage (for testing purposes, not part of the class itself)
async def _main_test_job_manager():
    # This is for basic self-testing; actual usage will be via UI/CLI
    print("Initializing JobManager...")
    job_manager = await JobManager.get_instance()

    # Simulate creating a job
    scan_job_db = await job_manager.create_job(
        job_type="scan_directory",
        target_path="./test_data", # Ensure this path exists for testing
        parameters={"recursive": True, "checksum": False}
    )
    print(f"Created scan job: {scan_job_db.id}")

    # Simulate starting the job
    await job_manager.start_job(scan_job_db.id)
    print(f"Started scan job: {scan_job_db.id}")

    # Monitor job progress (in a real app, UI would do this)
    while True:
        info = await job_manager.get_job_info(scan_job_db.id)
        if info:
            print(f"Job {info['id']} Status: {info['status']}, Progress: {info['progress']['processed_items']}/{info['progress']['total_items']} ({info['progress']['message']})")
            if info['status'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
                break
        await asyncio.sleep(1) # Check every second

    print("\nListing all jobs:")
    all_jobs = await job_manager.list_jobs()
    for job_info in all_jobs:
        print(f" - {job_info['id']} | {job_info['job_type']} | {job_info['status']} | Processed: {job_info['total_items_processed']}")

    # Create another job to demonstrate cancellation
    duplicate_job_db = await job_manager.create_job(
        job_type="find_duplicates",
        target_path="./large_data_set",
        parameters={"algorithm": "sha256"}
    )
    print(f"\nCreated duplicate job: {duplicate_job_db.id}")
    await job_manager.start_job(duplicate_job_db.id)
    print(f"Started duplicate job: {duplicate_job_db.id}")

    await asyncio.sleep(3) # Let it run for a bit
    print(f"Attempting to cancel duplicate job: {duplicate_job_db.id}")
    await job_manager.cancel_job(duplicate_job_db.id)

    # Monitor cancellation
    while True:
        info = await job_manager.get_job_info(duplicate_job_db.id)
        if info:
            print(f"Job {info['id']} Status: {info['status']}")
            if info['status'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
                break
        await asyncio.sleep(1)

    print("\nFinal listing of all jobs:")
    all_jobs = await job_manager.list_jobs()
    for job_info in all_jobs:
        print(f" - {job_info['id']} | {job_info['job_type']} | {job_info['status']} | Processed: {job_info['total_items_processed']}")


if __name__ == "__main__":
    # Ensure database models are accessible for testing
    # This part would typically be handled by a main app initialization
    # from sanchay_app.database.database_setup import create_db_and_tables
    # asyncio.run(create_db_and_tables()) # Example: if setup is async

    # For running direct tests of this file, you might need a mock sanchay_core
    # or ensure your Rust extension is built and available.
    # Also, ensure 'sanchay_app.database.models' and 'sanchay_app.database.connection'
    # are correctly set up for an in-memory or test SQLite DB.
    
    # In a real application, the main event loop would be started by PySide6 or CLI.
    # This is just for demonstration if run as a script.
    print("Running JobManager test...")
    # asyncio.run(_main_test_job_manager()) # Uncomment to run the test
    print("Test complete (or not run).")