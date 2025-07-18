import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import uuid

from celery.result import AsyncResult
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import necessary components from the backend application
from backend.src.karyaksham_workers.celery_app import celery_app
from backend.src.karyaksham_workers.tasks.processing import process_file_task
from backend.src.karyaksham_api.db.session import SessionLocal, Base # Assuming Base is imported in session.py
from backend.src.karyaksham_api.crud.crud_job import crud_job
from backend.src.karyaksham_api.schemas.job import JobCreate, JobStatus
from backend.src.karyaksham_api.db.models.job import Job as DBJob # SQLAlchemy model
from backend.src.karyaksham_api.core.config import settings # For mock settings like bucket

# --- Fixtures (Ideally placed in conftest.py for a real project) ---

# Mock environment variables for testing.
# This ensures settings are available for tests without requiring a .env file.
# In a real project, this might be handled by pytest-env or similar.
@pytest.fixture(scope="session", autouse=True)
def mock_settings():
    settings.configure(
        ENVIRONMENT="test",
        SECRET_KEY="test_secret_key_for_jwt_do_not_use_in_prod",
        POSTGRES_SERVER="localhost", # Will be mocked or use ephemeral DB
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_DB="test_karyakshamdb",
        REDIS_HOST="localhost", # Will be used for Celery broker/backend
        REDIS_PORT=6379,
        OBJECT_STORAGE_ENDPOINT="http://mocked-s3:9000",
        OBJECT_STORAGE_ACCESS_KEY="mock_access",
        OBJECT_STORAGE_SECRET_KEY="mock_secret",
        OBJECT_STORAGE_BUCKET="test-karyaksham-data"
    )
    yield

@pytest.fixture(scope="module")
def celery_session_app():
    """Configures and provides the Celery app instance for tests."""
    # Ensure Celery is in eager mode (synchronous execution) for debugging if needed,
    # but for true integration, it must be False.
    celery_app.conf.update(
        broker_url=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        result_backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        task_always_eager=False, # Crucial for asynchronous worker tests
        task_eager_propagates=False, # Do not re-raise exceptions in eager mode
        worker_hijack_root_logger=False, # Prevent worker from taking over logging
        task_serializer="json",
        accept_content=['json'],
        result_serializer="json",
        timezone='UTC',
        enable_utc=True,
    )
    return celery_app

@pytest.fixture(scope="module")
def celery_session_worker(celery_session_app):
    """Starts a Celery worker in a separate thread/process for the test session."""
    # Using 'solo' pool for simplicity in a test environment.
    # For more complex scenarios, consider 'gevent' or 'processes' if needed.
    # Note: For this to work, a Redis instance must be running on localhost:6379.
    with celery_session_app.connection() as connection:
        # Start the worker with a reduced concurrency for predictable testing
        worker = celery_session_app.Worker(
            app=celery_session_app,
            connection=connection,
            pool='solo',
            concurrency=1,
            loglevel='INFO',
            traceback=True,
            disable_rate_limits=True
        )
        worker.start()
        yield worker
        worker.stop()

@pytest.fixture(scope="function")
def db_session_fixture():
    """Provides a transactional database session for each test function.
    
    This fixture creates a clean database state for each test by
    rolling back transactions after the test completes.
    In a real project, this would typically use a dedicated test database
    URL to avoid polluting the development database.
    """
    # For integration tests, we want to hit a real DB, but keep it clean.
    # This assumes a test PostgreSQL is running and accessible via settings.
    # If not, use an in-memory SQLite for simpler unit-like tests.
    
    # Create a test engine and session.
    # This should ideally be configured to point to a test database (e.g., `postgresql://user:pass@host:port/test_db`)
    # For demonstration, we'll try to connect to the configured DB,
    # but actual cleanup/setup needs proper management (e.g., dropping/creating DB).
    # For now, rely on session.begin_nested() and rollback().
    
    # Example for an in-memory SQLite for lighter tests (replace for true PostgreSQL integration)
    # engine = create_engine("sqlite:///:memory:")
    # Base.metadata.create_all(bind=engine)
    # TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # db = TestingSessionLocal()

    db = SessionLocal() # Use the application's SessionLocal, which should point to test DB
    db.begin_nested() # Use nested transaction for rollback per test
    yield db
    db.rollback() # Rollback changes after test
    db.close()

@pytest.fixture(autouse=True)
def mock_rust_engine_processing(mocker):
    """
    Mocks the Rust engine's processing function that `processing.py` calls.
    This prevents actual Rust code execution and heavy I/O during Python integration tests.
    The patch target `backend.src.karyaksham_workers.tasks.processing.rust_process_data`
    assumes `processing.py` has an import like `from rust_engine_lib import process_data as rust_process_data`.
    """
    mock_func = mocker.patch("backend.src.karyaksham_workers.tasks.processing.rust_process_data")
    mock_func.return_value = None # Assume it returns None on success, or output path, etc.
    return mock_func

@pytest.fixture(autouse=True)
def mock_object_storage_client(mocker):
    """
    Mocks the `ObjectStorageClient` used by the Python application (if any).
    This handles potential S3 interactions made directly by Python code in the worker task.
    If the Rust engine handles all S3 I/O, this mock might not be directly hit by the processing logic,
    but it's good practice to mock all external dependencies.
    """
    mock_client_instance = MagicMock()
    # Mock methods that might be called by Python code
    mock_client_instance.upload_file_content.return_value = None
    mock_client_instance.get_presigned_download_url.return_value = "http://mocked.s3/download"
    mock_client_instance.get_presigned_upload_url.return_value = "http://mocked.s3/upload"

    # Patch the `ObjectStorageClient` constructor or the instance used in `processing.py`
    mocker.patch("backend.src.karyaksham_workers.tasks.processing.ObjectStorageClient",
                 return_value=mock_client_instance)

    return mock_client_instance


# --- Integration Tests ---

def test_processing_job_success(
    celery_session_worker,
    db_session_fixture: Session,
    mock_rust_engine_processing: MagicMock,
    mock_object_storage_client: MagicMock
):
    """
    Tests the end-to-end flow of a successful processing job via Celery worker.
    Verifies task execution, database status updates, and Rust engine call.
    """
    user_id = 1 # Dummy user ID for the job
    input_s3_path = f"s3://{settings.OBJECT_STORAGE_BUCKET}/user_{user_id}/input/test_file_input.csv"
    output_s3_path = f"s3://{settings.OBJECT_STORAGE_BUCKET}/user_{user_id}/output/{uuid.uuid4()}.csv"
    processing_params = {"filter": {"column": "status", "value": "active"}, "format": "parquet"}

    # 1. Create a job entry in the database with PENDING status
    job_in_db = crud_job.create(db_session_fixture, obj_in=JobCreate(
        user_id=user_id,
        input_file_path=input_s3_path,
        output_file_path=None, # Initially null, to be filled by worker
        job_type="csv_filter",
        status=JobStatus.PENDING,
        parameters=processing_params
    ))
    job_id = job_in_db.id

    assert job_in_db.status == JobStatus.PENDING
    assert job_in_db.output_file_path is None
    assert job_in_db.completed_at is None

    # 2. Enqueue the processing task to Celery
    task: AsyncResult = process_file_task.delay(
        job_id=job_id,
        input_path=input_s3_path,
        output_path=output_s3_path,
        processing_params=processing_params
    )

    # 3. Wait for the task to complete asynchronously
    # Using task.get() blocks until the result is ready or timeout occurs.
    try:
        task_result = task.get(timeout=15) # Increased timeout for potential worker startup/processing simulation
        assert task.status == 'SUCCESS'
    except Exception as e:
        # If the task fails for any reason during the test, this will catch it.
        pytest.fail(f"Celery task failed with exception: {e}, final status: {task.status}, traceback: {task.traceback}")

    # 4. Verify job status and output path in the database
    # Refresh the job object from the database to get the latest status
    updated_job: DBJob = crud_job.get(db_session_fixture, id=job_id)
    assert updated_job is not None
    assert updated_job.id == job_id
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.output_file_path == output_s3_path
    assert updated_job.completed_at is not None # Should be set upon completion
    assert updated_job.updated_at > job_in_db.updated_at # Ensure update timestamp changed

    # 5. Verify the Rust engine's processing function was called correctly
    mock_rust_engine_processing.assert_called_once_with(
        input_s3_path,
        output_s3_path,
        processing_params
    )

    # 6. Verify ObjectStorageClient methods were not directly called by the task
    # because `mock_rust_engine_processing` implies Rust handles the actual I/O.
    # If the Python worker task had explicit calls to `ObjectStorageClient` after
    # calling the Rust function (e.g., for metadata), they would be asserted here.
    mock_object_storage_client.upload_file_content.assert_not_called()
    mock_object_storage_client.get_presigned_download_url.assert_not_called()


def test_processing_job_failure(
    celery_session_worker,
    db_session_fixture: Session,
    mock_rust_engine_processing: MagicMock
):
    """
    Tests the end-to-end flow of a failed processing job via Celery worker.
    Verifies task failure, retry mechanism, and database status update.
    """
    user_id = 1
    input_s3_path = f"s3://{settings.OBJECT_STORAGE_BUCKET}/user_{user_id}/input/invalid_file.csv"
    output_s3_path = f"s3://{settings.OBJECT_STORAGE_BUCKET}/user_{user_id}/output/{uuid.uuid4()}.csv"
    processing_params = {"bad_param": "value"}

    # Simulate the Rust engine raising an error. This will cause the Celery task to fail.
    mock_rust_engine_processing.side_effect = ValueError("Simulated Rust processing error")

    # 1. Create a job entry in the database
    job_in_db = crud_job.create(db_session_fixture, obj_in=JobCreate(
        user_id=user_id,
        input_file_path=input_s3_path,
        output_file_path=None,
        job_type="csv_process",
        status=JobStatus.PENDING,
        parameters=processing_params
    ))
    job_id = job_in_db.id

    # 2. Enqueue the task
    task: AsyncResult = process_file_task.delay(
        job_id=job_id,
        input_path=input_s3_path,
        output_path=output_s3_path,
        processing_params=processing_params
    )

    # 3. Wait for the task to complete (or fail after retries)
    # The task has max_retries=3. It will attempt 1 (initial) + 3 (retries) = 4 times.
    try:
        task.get(timeout=20) # Give it enough time for all retries + delays
        pytest.fail("Celery task unexpectedly succeeded, it should have failed.")
    except Exception as e:
        # Expected behavior: the task's final status is FAILED, and the exception is propagated
        assert task.status == 'FAILURE'
        assert "Simulated Rust processing error" in str(e)

    # 4. Verify job status in the database is FAILED
    updated_job: DBJob = crud_job.get(db_session_fixture, id=job_id)
    assert updated_job is not None
    assert updated_job.id == job_id
    assert updated_job.status == JobStatus.FAILED
    assert updated_job.output_file_path is None # Should remain None on failure
    assert updated_job.completed_at is None # Should not have a completed timestamp

    # 5. Verify the Rust engine was called multiple times due to retries
    # It should be called once for the initial attempt, plus once for each retry.
    assert mock_rust_engine_processing.call_count == (1 + process_file_task.max_retries)


def test_processing_job_not_found(
    celery_session_worker,
    db_session_fixture: Session,
    mock_rust_engine_processing: MagicMock
):
    """
    Tests handling of a processing job where the `job_id` passed to the task
    does not exist in the database. The task should fail gracefully.
    """
    non_existent_job_id = 99999
    user_id = 1 # Irrelevant as job ID is primary
    input_s3_path = f"s3://{settings.OBJECT_STORAGE_BUCKET}/user_{user_id}/input/test.csv"
    output_s3_path = f"s3://{settings.OBJECT_STORAGE_BUCKET}/user_{user_id}/output/{uuid.uuid4()}.csv"
    processing_params = {}

    # Ensure the job does NOT exist in the database
    initial_job_count = crud_job.count(db_session_fixture)

    # Enqueue the task with a non-existent job ID
    task: AsyncResult = process_file_task.delay(
        job_id=non_existent_job_id,
        input_path=input_s3_path,
        output_path=output_s3_path,
        processing_params=processing_params
    )

    # Wait for the task to fail
    try:
        task.get(timeout=5)
        pytest.fail("Celery task unexpectedly succeeded. It should have failed due to job_id not found.")
    except Exception as e:
        assert task.status == 'FAILURE'
        # The task should raise a ValueError if job is not found
        assert f"Job with ID {non_existent_job_id} not found." in str(e)

    # Verify the Rust engine was NOT called at all, as the job was not found early
    mock_rust_engine_processing.assert_not_called()

    # Verify no new jobs were created and existing count is same
    assert crud_job.count(db_session_fixture) == initial_job_count