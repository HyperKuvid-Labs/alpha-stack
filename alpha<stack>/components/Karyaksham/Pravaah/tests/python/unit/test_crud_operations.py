import pytest
from unittest.mock import MagicMock, patch

from karyaksham_api.db.models.user import User
from karyaksham_api.db.models.job import Job
from karyaksham_api.schemas.user import UserCreate, UserUpdate
from karyaksham_api.schemas.job import JobCreate, JobUpdate, JobStatus

from karyaksham_api.crud.crud_user import user as crud_user
from karyaksham_api.crud.crud_job import job as crud_job


@pytest.fixture
def mock_db_session():
    """Provides a mocked SQLAlchemy session with chainable query mocks."""
    mock_session = MagicMock()
    
    # Create a chainable mock for query results
    mock_query_result = MagicMock()
    mock_query_result.filter.return_value = mock_query_result
    mock_query_result.filter_by.return_value = mock_query_result
    mock_query_result.offset.return_value = mock_query_result
    mock_query_result.limit.return_value = mock_query_result
    
    # Default return values for terminal methods
    mock_query_result.first.return_value = None
    mock_query_result.all.return_value = []
    
    mock_session.query.return_value = mock_query_result
    
    yield mock_session
    mock_session.reset_mock()


# --- Unit Tests for User CRUD Operations ---

def test_create_user(mock_db_session):
    """Test creating a new user."""
    user_in = UserCreate(email="test@example.com", password="secure_password")
    
    # Simulate ID assignment on refresh (often done by ORM after commit)
    mock_db_session.refresh.side_effect = lambda x: setattr(x, 'id', 1)

    with patch('karyaksham_api.auth.security.get_password_hash', return_value="hashed_secure_password"):
        user = crud_user.create(mock_db_session, obj_in=user_in)

    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(user)

    assert user.email == user_in.email
    assert user.hashed_password == "hashed_secure_password"
    assert user.id == 1


def test_get_user(mock_db_session):
    """Test retrieving a user by ID."""
    expected_user = User(id=1, email="existing@example.com", hashed_password="hashed_password")
    mock_db_session.query.return_value.filter.return_value.first.return_value = expected_user
    
    user = crud_user.get(mock_db_session, id=1)
    
    mock_db_session.query.assert_called_once_with(User)
    mock_db_session.query.return_value.filter.assert_called_once() # Args for filter will be checked by crud method
    assert user == expected_user


def test_get_user_not_found(mock_db_session):
    """Test retrieving a user that does not exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    user = crud_user.get(mock_db_session, id=999)
    assert user is None


def test_get_user_by_email(mock_db_session):
    """Test retrieving a user by email."""
    expected_user = User(id=1, email="existing@example.com", hashed_password="hashed_password")
    mock_db_session.query.return_value.filter.return_value.first.return_value = expected_user
    
    user = crud_user.get_by_email(mock_db_session, email="existing@example.com")
    
    mock_db_session.query.assert_called_once_with(User)
    mock_db_session.query.return_value.filter.assert_called_once()
    assert user == expected_user


def test_update_user(mock_db_session):
    """Test updating an existing user."""
    existing_user = User(id=1, email="old@example.com", hashed_password="old_password")
    user_update_in = UserUpdate(email="new@example.com", password="new_secure_password")
    
    # Set the current state for the update target
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_user

    with patch('karyaksham_api.auth.security.get_password_hash', return_value="hashed_new_password"):
        updated_user = crud_user.update(mock_db_session, db_obj=existing_user, obj_in=user_update_in)
    
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(existing_user)
    
    assert updated_user.email == "new@example.com"
    assert updated_user.hashed_password == "hashed_new_password"
    assert updated_user.id == existing_user.id


def test_remove_user(mock_db_session):
    """Test removing a user."""
    user_to_remove = User(id=1, email="remove@example.com", hashed_password="hashed_password")
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = user_to_remove
    
    removed_user = crud_user.remove(mock_db_session, id=1)
    
    mock_db_session.delete.assert_called_once_with(user_to_remove)
    mock_db_session.commit.assert_called_once()
    assert removed_user == user_to_remove


# --- Unit Tests for Job CRUD Operations ---

def test_create_job(mock_db_session):
    """Test creating a new job."""
    job_in = JobCreate(
        user_id=1, 
        input_path="s3://bucket/input.csv", 
        output_path="s3://bucket/output.parquet", 
        status=JobStatus.PENDING,
        parameters={"filter_col": "value"}
    )
    
    mock_db_session.refresh.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

    job = crud_job.create(mock_db_session, obj_in=job_in)
    
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(job)
    
    assert job.user_id == job_in.user_id
    assert job.input_path == job_in.input_path
    assert job.status == JobStatus.PENDING
    assert job.id == 1


def test_get_job(mock_db_session):
    """Test retrieving a job by ID."""
    expected_job = Job(id=1, user_id=1, input_path="s3://in.csv", output_path="s3://out.csv", status=JobStatus.COMPLETED)
    mock_db_session.query.return_value.filter.return_value.first.return_value = expected_job
    
    job = crud_job.get(mock_db_session, id=1)
    
    mock_db_session.query.assert_called_once_with(Job)
    mock_db_session.query.return_value.filter.assert_called_once()
    assert job == expected_job


def test_get_job_not_found(mock_db_session):
    """Test retrieving a job that does not exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    job = crud_job.get(mock_db_session, id=999)
    assert job is None


def test_update_job(mock_db_session):
    """Test updating an existing job."""
    existing_job = Job(id=1, user_id=1, input_path="s3://in.csv", output_path="s3://out.csv", status=JobStatus.PENDING)
    job_update_in = JobUpdate(status=JobStatus.RUNNING, output_path="s3://new_out.parquet")
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_job
    
    updated_job = crud_job.update(mock_db_session, db_obj=existing_job, obj_in=job_update_in)
    
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(existing_job)
    
    assert updated_job.status == JobStatus.RUNNING
    assert updated_job.output_path == "s3://new_out.parquet"
    assert updated_job.id == existing_job.id


def test_remove_job(mock_db_session):
    """Test removing a job."""
    job_to_remove = Job(id=1, user_id=1, input_path="s3://in.csv", output_path="s3://out.csv", status=JobStatus.COMPLETED)
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = job_to_remove
    
    removed_job = crud_job.remove(mock_db_session, id=1)
    
    mock_db_session.delete.assert_called_once_with(job_to_remove)
    mock_db_session.commit.assert_called_once()
    assert removed_job == job_to_remove


def test_get_multi_jobs_by_user(mock_db_session):
    """Test retrieving multiple jobs by user ID."""
    user_id = 1
    jobs_for_user = [
        Job(id=1, user_id=user_id, input_path="s3://job1.csv", status=JobStatus.COMPLETED),
        Job(id=2, user_id=user_id, input_path="s3://job2.csv", status=JobStatus.RUNNING),
    ]
    
    # Configure the chained mock for get_multi_by_owner
    mock_db_session.query.return_value.filter_by.return_value.offset.return_value.limit.return_value.all.return_value = jobs_for_user

    jobs = crud_job.get_multi_by_owner(mock_db_session, owner_id=user_id, skip=0, limit=10)
    
    mock_db_session.query.assert_called_once_with(Job)
    mock_db_session.query.return_value.filter_by.assert_called_once_with(user_id=user_id)
    mock_db_session.query.return_value.filter_by.return_value.offset.assert_called_once_with(0)
    mock_db_session.query.return_value.filter_by.return_value.offset.return_value.limit.assert_called_once_with(10)
    
    assert jobs == jobs_for_user
    assert len(jobs) == 2