import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest import mock
import jwt
from datetime import datetime, timedelta, timezone

from karyaksham_api.main import app
from karyaksham_api.db.session import get_db
from karyaksham_api.db.models.user import User
from karyaksham_api.db.models.job import Job
from karyaksham_api.schemas.user import UserCreate, UserLogin, UserResponse, UserUpdate
from karyaksham_api.schemas.job import JobCreate, JobResponse, JobStatus
from karyaksham_api.crud.crud_user import user as crud_user
from karyaksham_api.core.config import settings
from karyaksham_api.auth import security
from karyaksham_api.integrations.object_storage import ObjectStorageClient
from karyaksham_workers.celery_app import celery_app as celery_app_instance


# Assume 'client' and 'db' fixtures are provided by conftest.py
# If not, they would need to be defined here,
# e.g., using an in-memory SQLite for 'db' and TestClient for 'app'.

# Example for reference if conftest.py was not used, or for local fixtures:
# @pytest.fixture(scope="module")
# def test_app():
#     # Override the get_db dependency to use an in-memory SQLite for tests
#     def override_get_db():
#         engine = create_engine("sqlite:///./test.db") # Or in-memory: "sqlite:///:memory:"
#         TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#         Base.metadata.create_all(bind=engine) # Create tables
#         db_session = TestingSessionLocal()
#         try:
#             yield db_session
#         finally:
#             db_session.close()
#             # Base.metadata.drop_all(bind=engine) # Optional: drop tables after tests
#
#     app.dependency_overrides[get_db] = override_get_db
#     with TestClient(app) as client:
#         yield client
#     app.dependency_overrides.clear()
#
# @pytest.fixture
# def db(test_app): # depends on test_app to ensure overrides are in place
#     with next(get_db()) as session: # Get a session using the overridden dependency
#         yield session
#         # Teardown: Rollback changes after each test to ensure clean state
#         session.rollback()
#         # Clean up specific data if using a persistent test DB
#         for tbl in reversed(Base.metadata.sorted_tables):
#             session.execute(tbl.delete())
#         session.commit()


@pytest.fixture
def test_user_data():
    """Provides a dictionary for creating a test user."""
    return {
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def registered_user(db: Session, test_user_data: dict) -> User:
    """Creates and registers a user in the test database."""
    user_in = UserCreate(**test_user_data)
    user = crud_user.create(db, obj_in=user_in)
    yield user
    # Clean up: delete user after test
    db.delete(user)
    db.commit()


@pytest.fixture
def auth_headers(registered_user: User) -> dict:
    """Generates authentication headers for the registered test user."""
    token = security.create_access_token(registered_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_client(client: TestClient, auth_headers: dict) -> TestClient:
    """Returns a TestClient with authentication headers pre-set."""
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def mock_object_storage_presigned_url(mocker):
    """Mocks the create_presigned_url method of ObjectStorageClient."""
    mock_url = "http://mock-s3-presigned-url/test-file.csv"
    mocker.patch(
        "karyaksham_api.integrations.object_storage.ObjectStorageClient.create_presigned_url",
        return_value=mock_url,
    )
    return mock_url


@pytest.fixture
def mock_celery_task_dispatch(mocker):
    """Mocks the send_task method of the Celery app instance."""
    mock_async_result = mock.MagicMock()
    mock_async_result.id = "mock_task_id_123"
    mock_async_result.status = "PENDING"
    mocker.patch.object(celery_app_instance, "send_task", return_value=mock_async_result)
    return mock_async_result.id


class TestAuthEndpoints:
    def test_register_user_success(self, client: TestClient, db: Session, test_user_data: dict):
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 200
        user_response = UserResponse(**response.json())
        assert user_response.email == test_user_data["email"]
        assert user_response.full_name == test_user_data["full_name"]
        assert user_response.id is not None

        # Verify user is in DB
        db_user = crud_user.get_by_email(db, email=test_user_data["email"])
        assert db_user is not None
        assert db_user.email == test_user_data["email"]

    def test_register_user_duplicate_email(self, client: TestClient, registered_user: User, test_user_data: dict):
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 400
        assert "User with this email already exists" in response.json()["detail"]

    def test_login_for_access_token_success(self, client: TestClient, registered_user: User, test_user_data: dict):
        login_data = {
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
        response = client.post("/api/v1/auth/token", data=login_data)
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

        # Verify token content (optional, but good for integration)
        decoded_token = jwt.decode(
            token_data["access_token"],
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
            options={"verify_aud": False},
        )
        assert decoded_token["sub"] == registered_user.email

    def test_login_for_access_token_bad_credentials(self, client: TestClient, registered_user: User):
        login_data = {
            "username": registered_user.email,
            "password": "wrongpassword",
        }
        response = client.post("/api/v1/auth/token", data=login_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_get_current_user_me_authenticated(self, authenticated_client: TestClient, registered_user: User):
        response = authenticated_client.get("/api/v1/users/me")
        assert response.status_code == 200
        user_response = UserResponse(**response.json())
        assert user_response.id == registered_user.id
        assert user_response.email == registered_user.email

    def test_get_current_user_me_unauthenticated(self, client: TestClient):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"


class TestUserEndpoints:
    def test_update_user_me_success(self, authenticated_client: TestClient, db: Session, registered_user: User):
        update_data = {"full_name": "Updated Test User"}
        response = authenticated_client.put("/api/v1/users/me", json=update_data)
        assert response.status_code == 200
        user_response = UserResponse(**response.json())
        assert user_response.full_name == update_data["full_name"]

        # Verify update in DB
        db.refresh(registered_user)
        assert registered_user.full_name == update_data["full_name"]

    def test_update_user_me_unauthenticated(self, client: TestClient):
        update_data = {"full_name": "Updated Test User"}
        response = client.put("/api/v1/users/me", json=update_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"


class TestJobEndpoints:
    def test_create_job_success(
        self,
        authenticated_client: TestClient,
        db: Session,
        registered_user: User,
        mock_object_storage_presigned_url: str,
        mock_celery_task_dispatch: str,
        mocker,
    ):
        job_create_data = {
            "filename": "test_data.csv",
            "file_size_bytes": 1024,
            "original_path": "path/to/original/test_data.csv",
            "processing_parameters": {"filter": "column == 'value'"},
            "output_format": "parquet",
        }
        response = authenticated_client.post("/api/v1/jobs/", json=job_create_data)

        assert response.status_code == 200
        job_response = JobResponse(**response.json())

        assert job_response.filename == job_create_data["filename"]
        assert job_response.status == JobStatus.PENDING
        assert job_response.owner_id == registered_user.id
        assert job_response.input_presigned_url == mock_object_storage_presigned_url
        assert job_response.celery_task_id == mock_celery_task_dispatch

        # Verify job is in DB
        db_job = db.query(Job).filter(Job.id == job_response.id).first()
        assert db_job is not None
        assert db_job.filename == job_create_data["filename"]
        assert db_job.status == JobStatus.PENDING

        # Verify external calls were made
        ObjectStorageClient.create_presigned_url.assert_called_once()
        celery_app_instance.send_task.assert_called_once_with(
            "karyaksham_workers.tasks.processing.process_file_task",
            kwargs={
                "job_id": job_response.id,
                "input_s3_path": job_create_data["original_path"],
                "processing_params": job_create_data["processing_parameters"],
                "output_format": job_create_data["output_format"],
                "owner_id": registered_user.id,
            },
        )

    def test_create_job_unauthenticated(self, client: TestClient, mock_object_storage_presigned_url, mock_celery_task_dispatch):
        job_create_data = {
            "filename": "test_data.csv",
            "file_size_bytes": 1024,
            "original_path": "path/to/original/test_data.csv",
            "processing_parameters": {"filter": "column == 'value'"},
            "output_format": "parquet",
        }
        response = client.post("/api/v1/jobs/", json=job_create_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_get_jobs_list_success(self, authenticated_client: TestClient, db: Session, registered_user: User):
        # Create a few jobs for the user
        job1 = Job(
            filename="job1.csv",
            owner_id=registered_user.id,
            status=JobStatus.COMPLETED,
            original_path="s3://bucket/job1.csv",
            output_path="s3://bucket/processed/job1.parquet",
            file_size_bytes=1000,
            processing_parameters={},
            output_format="parquet",
            celery_task_id="task1"
        )
        job2 = Job(
            filename="job2.csv",
            owner_id=registered_user.id,
            status=JobStatus.RUNNING,
            original_path="s3://bucket/job2.csv",
            file_size_bytes=2000,
            processing_parameters={},
            output_format="parquet",
            celery_task_id="task2"
        )
        db.add_all([job1, job2])
        db.commit()
        db.refresh(job1)
        db.refresh(job2)

        response = authenticated_client.get("/api/v1/jobs/")
        assert response.status_code == 200
        jobs = [JobResponse(**j) for j in response.json()]
        assert len(jobs) == 2
        assert any(j.filename == "job1.csv" for j in jobs)
        assert any(j.filename == "job2.csv" for j in jobs)

    def test_get_job_by_id_success(self, authenticated_client: TestClient, db: Session, registered_user: User):
        job = Job(
            filename="single_job.csv",
            owner_id=registered_user.id,
            status=JobStatus.PENDING,
            original_path="s3://bucket/single_job.csv",
            file_size_bytes=500,
            processing_parameters={},
            output_format="csv",
            celery_task_id="single_task"
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        response = authenticated_client.get(f"/api/v1/jobs/{job.id}")
        assert response.status_code == 200
        job_response = JobResponse(**response.json())
        assert job_response.id == job.id
        assert job_response.filename == job.filename
        assert job_response.owner_id == registered_user.id

    def test_get_job_by_id_not_found(self, authenticated_client: TestClient):
        response = authenticated_client.get("/api/v1/jobs/99999") # Non-existent ID
        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    def test_get_job_by_id_unauthorized_access(self, authenticated_client: TestClient, db: Session):
        # Create a job owned by a different user
        other_user_data = {
            "email": "other@example.com",
            "password": "otherpassword",
            "full_name": "Other User",
        }
        other_user = crud_user.create(db, obj_in=UserCreate(**other_user_data))
        
        other_job = Job(
            filename="other_user_job.csv",
            owner_id=other_user.id,
            status=JobStatus.COMPLETED,
            original_path="s3://bucket/other_job.csv",
            file_size_bytes=1000,
            processing_parameters={},
            output_format="parquet",
            celery_task_id="other_task"
        )
        db.add(other_job)
        db.commit()
        db.refresh(other_job)

        response = authenticated_client.get(f"/api/v1/jobs/{other_job.id}")
        assert response.status_code == 404 # User should not know it exists or not
        assert response.json()["detail"] == "Job not found"

        # Clean up other user and job
        db.delete(other_job)
        db.delete(other_user)
        db.commit()