from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import models and schemas used by app.core.jobs
from app.api.v1.schemas import JobCreate
from app.db.models.job import Job, JobStatus
from app.core import jobs
from app.core.exceptions import JobNotFoundException, JobProcessingException


# Fixture for a mock database session
@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    session = MagicMock()
    # Configure mock behavior for common session methods
    session.add.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None
    session.rollback.return_value = None

    # Mock query object chain for get/filter operations
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.filter_by.return_value = mock_query
    mock_query.first.return_value = None  # Default for single object retrieval
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []  # Default for multiple object retrieval

    return session


# Fixture for a mock pravah_core engine (Rust bridge)
@pytest.fixture
def mock_pravah_core_engine():
    """Mocks the Rust core engine module within the app.core.jobs context."""
    # `patch` targets where the object is looked up, so if jobs.py does `import pravah_core`,
    # then `patch('app.core.jobs.pravah_core')` is correct.
    with patch('app.core.jobs.pravah_core', autospec=True) as mock_core:
        # Assuming pravah_core exposes `engine` which has `process_files_async`
        mock_core.engine.process_files_async = AsyncMock()
        yield mock_core


# Fixture for a sample JobCreate schema
@pytest.fixture
def sample_job_create_data():
    """Provides sample data for creating a job."""
    return JobCreate(
        input_path="/data/input/my_files",
        output_path="/data/output/processed_files",
        job_type="csv_header_extraction",
        config={"delimiter": ",", "max_rows": 100}
    )


# Fixture for a sample Job ORM model instance
@pytest.fixture
def sample_job_model(sample_job_create_data):
    """Provides a sample Job ORM model instance."""
    job_id = uuid4()
    now = datetime.now(timezone.utc)
    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        input_path=sample_job_create_data.input_path,
        output_path=sample_job_create_data.output_path,
        job_type=sample_job_create_data.job_type,
        config=sample_job_create_data.config,
        created_at=now,
        updated_at=now
    )
    return job


class TestJobCore:

    def test_create_job_success(self, mock_db_session, sample_job_create_data):
        """Test successful job creation."""
        # Simulate the DB assigning an ID after add/commit
        mock_db_session.add.side_effect = lambda x: setattr(x, 'id', uuid4())

        created_job = jobs.create_job(mock_db_session, sample_job_create_data)

        # Assertions
        assert created_job is not None
        assert isinstance(created_job.id, UUID)
        assert created_job.status == JobStatus.PENDING
        assert created_job.input_path == sample_job_create_data.input_path
        assert created_job.job_type == sample_job_create_data.job_type
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(created_job)

    def test_get_job_by_id_success(self, mock_db_session, sample_job_model):
        """Test retrieving a job by its ID successfully."""
        mock_db_session.query().filter_by().first.return_value = sample_job_model

        retrieved_job = jobs.get_job(mock_db_session, sample_job_model.id)

        assert retrieved_job == sample_job_model
        mock_db_session.query.assert_called_once_with(Job)
        mock_db_session.query().filter_by.assert_called_once_with(id=sample_job_model.id)
        mock_db_session.query().filter_by().first.assert_called_once()

    def test_get_job_by_id_not_found(self, mock_db_session):
        """Test retrieving a job that does not exist."""
        mock_db_session.query().filter_by().first.return_value = None
        non_existent_id = uuid4()

        with pytest.raises(JobNotFoundException):
            jobs.get_job(mock_db_session, non_existent_id)

        mock_db_session.query().filter_by().first.assert_called_once()

    def test_get_all_jobs_success(self, mock_db_session, sample_job_model):
        """Test retrieving multiple jobs."""
        job2 = Job(
            id=uuid4(), status=JobStatus.COMPLETED, input_path="/path2", output_path="/out2",
            job_type="resize_images", config={}, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
        )
        mock_db_session.query().all.return_value = [sample_job_model, job2]

        all_jobs = jobs.get_jobs(mock_db_session, skip=0, limit=10)

        assert len(all_jobs) == 2
        assert all_jobs[0] == sample_job_model
        assert all_jobs[1] == job2
        mock_db_session.query.assert_called_once_with(Job)
        mock_db_session.query().offset.assert_called_once_with(0)
        mock_db_session.query().limit.assert_called_once_with(10)
        mock_db_session.query().all.assert_called_once()

    def test_update_job_status_and_details_success(self, mock_db_session, sample_job_model):
        """Test updating job status and details."""
        mock_db_session.query().filter_by().first.return_value = sample_job_model

        updated_job = jobs.update_job_status_and_details(
            mock_db_session, sample_job_model.id, JobStatus.COMPLETED,
            result_path="/output/result.txt", error_message=None
        )

        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.result_path == "/output/result.txt"
        assert updated_job.error_message is None
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(updated_job)

    def test_update_job_status_and_details_job_not_found(self, mock_db_session):
        """Test updating a job that does not exist."""
        mock_db_session.query().filter_by().first.return_value = None
        non_existent_id = uuid4()

        with pytest.raises(JobNotFoundException):
            jobs.update_job_status_and_details(
                mock_db_session, non_existent_id, JobStatus.COMPLETED
            )
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_initiate_job_processing_success(self, mock_db_session, sample_job_model):
        """Test successful initiation of job processing (scheduling the background task)."""
        sample_job_model.status = JobStatus.PENDING  # Ensure initial status for this test
        mock_db_session.query().filter_by().first.return_value = sample_job_model

        with patch('asyncio.create_task', new_callable=MagicMock) as mock_create_task:
            # Mock the coroutine that create_task would return
            mock_coro = AsyncMock()
            mock_create_task.return_value = mock_coro

            await jobs.initiate_job_processing(mock_db_session, sample_job_model.id)

            # Assert that job status was updated to RUNNING and committed
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(sample_job_model)
            assert sample_job_model.status == JobStatus.RUNNING

            # Assert that an async task was created
            mock_create_task.assert_called_once()
            # Verify the arguments passed to _run_processing_task
            args, _ = mock_create_task.call_args
            assert args[0].__name__ == '_run_processing_task'
            # Note: Checking closure variables can be brittle, but confirms the session is passed
            # assert args[0].__closure__[0].cell_contents == mock_db_session

    @pytest.mark.asyncio
    async def test_initiate_job_processing_not_found(self, mock_db_session):
        """Test initiating job processing for a non-existent job."""
        mock_db_session.query().filter_by().first.return_value = None
        non_existent_id = uuid4()

        with pytest.raises(JobNotFoundException):
            await jobs.initiate_job_processing(mock_db_session, non_existent_id)

        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_processing_task_success(self, mock_db_session, mock_pravah_core_engine, sample_job_model):
        """Test the internal _run_processing_task logic when Rust engine succeeds."""
        # Set up initial state for the job as if it's already running
        sample_job_model.status = JobStatus.RUNNING
        mock_db_session.query().filter_by().first.return_value = sample_job_model

        rust_success_result = {
            "success": True,
            "processed_count": 100,
            "failed_count": 0,
            "result_summary_path": "/some/output/summary.json"
        }
        mock_pravah_core_engine.engine.process_files_async.return_value = AsyncMock(return_value=rust_success_result)

        await jobs._run_processing_task(mock_db_session, sample_job_model.id)

        # Assertions
        mock_pravah_core_engine.engine.process_files_async.assert_called_once_with(
            input_path=sample_job_model.input_path,
            output_path=sample_job_model.output_path,
            job_type=sample_job_model.job_type,
            config=sample_job_model.config
        )
        assert sample_job_model.status == JobStatus.COMPLETED
        assert sample_job_model.result_path == rust_success_result["result_summary_path"]
        assert sample_job_model.error_message is None
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_processing_task_failure_from_engine(self, mock_db_session, mock_pravah_core_engine, sample_job_model):
        """Test _run_processing_task when the Rust engine reports a functional failure."""
        sample_job_model.status = JobStatus.RUNNING
        mock_db_session.query().filter_by().first.return_value = sample_job_model

        rust_failure_result = {
            "success": False,
            "error_message": "Failed to process files due to permission denied.",
            "processed_count": 0,
            "failed_count": 5,
            "result_summary_path": None
        }
        mock_pravah_core_engine.engine.process_files_async.return_value = AsyncMock(return_value=rust_failure_result)

        await jobs._run_processing_task(mock_db_session, sample_job_model.id)

        assert sample_job_model.status == JobStatus.FAILED
        assert sample_job_model.result_path is None
        assert sample_job_model.error_message == rust_failure_result["error_message"]
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_processing_task_exception_handling(self, mock_db_session, mock_pravah_core_engine, sample_job_model):
        """Test _run_processing_task when an unexpected Python exception occurs."""
        sample_job_model.status = JobStatus.RUNNING
        mock_db_session.query().filter_by().first.return_value = sample_job_model

        # Simulate an exception during the Rust engine call or any subsequent Python logic
        mock_pravah_core_engine.engine.process_files_async.side_effect = Exception("Simulated unexpected internal error!")

        await jobs._run_processing_task(mock_db_session, sample_job_model.id)

        assert sample_job_model.status == JobStatus.FAILED
        assert "Simulated unexpected internal error!" in sample_job_model.error_message
        assert sample_job_model.result_path is None
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
        # Expect rollback if the job status update itself fails, but here it commits the FAILED state.