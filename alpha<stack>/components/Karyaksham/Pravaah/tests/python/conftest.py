import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy_utils import database_exists, create_database, drop_database

# Import application components
from karyaksham_api.main import app
from karyaksham_api.core.config import settings
from karyaksham_api.db.session import get_db, Base
from karyaksham_api.db.models.user import User
from karyaksham_api.schemas.user import UserCreate
from karyaksham_api.crud.crud_user import crud_user
from karyaksham_api.auth.security import create_access_token # For creating test JWTs
from karyaksham_api.integrations.object_storage import ObjectStorageClient
from karyaksham_workers.celery_app import celery_app as celery_worker_app

# For mocking S3/MinIO
import boto3
from moto import mock_aws
from unittest.mock import MagicMock

# --- Test Database Configuration ---
# Construct a unique test database URL based on existing settings
# This ensures that tests run against a separate database.
test_db_name = f"{settings.POSTGRES_DB}_test"
TEST_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{test_db_name}"

@pytest.fixture(scope="session", autouse=True)
def apply_test_settings():
    """
    Fixture to apply test-specific settings globally for the entire test session.
    - Sets the environment to 'testing'.
    - Updates the JWT secret key for testing.
    - Configures Celery to run tasks synchronously (eagerly).
    """
    settings.ENVIRONMENT = "testing"
    # Ensure a sufficiently long secret key for JWTs in tests
    settings.SECRET_KEY = "supersecretkey_for_testing_karyaksham_jwt_do_not_use_in_prod" 
    
    # Configure Celery to run tasks locally and synchronously for tests
    # This avoids needing a running Redis and Celery worker for most backend tests.
    celery_worker_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)


@pytest.fixture(scope="session")
def db_engine():
    """
    Fixture to set up and tear down a test database for the entire test session.
    Creates all tables before tests run and drops them after.
    """
    engine = create_engine(TEST_DATABASE_URL)

    # Create the test database if it does not exist
    if not database_exists(engine.url):
        create_database(engine.url)

    # Create all tables defined in our SQLAlchemy models
    Base.metadata.create_all(bind=engine)

    yield engine

    # Drop the test database after the session is complete
    Base.metadata.drop_all(bind=engine)
    if database_exists(engine.url):
        drop_database(engine.url)


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Fixture to provide a clean, isolated database session for each test function.
    Each test runs within a transaction that is rolled back upon completion,
    ensuring a clean state for subsequent tests.
    """
    # Establish a connection and begin a transaction
    connection = db_engine.connect()
    transaction = connection.begin()
    
    # Create a session bound to the transaction
    # This ensures that all operations within the test function are part of this transaction
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestSessionLocal()

    # Override the `get_db` dependency in the FastAPI application to use our test session
    def override_get_db():
        try:
            yield session
        finally:
            # Ensure the session is closed after the dependency is used
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # After the test function finishes, roll back the transaction
    # and close the connection, discarding any changes made by the test.
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """
    Fixture to provide a TestClient instance for the FastAPI application.
    This client allows making requests to the API endpoints during tests.
    Scoped to 'module' for efficiency, as the application instance typically doesn't change.
    """
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """
    Fixture to create and return a regular test user in the database.
    This user can be used to test endpoints requiring authentication.
    """
    user_in = UserCreate(
        email="test_user@example.com",
        password="testpassword123",
        full_name="Test User",
    )
    # Use the existing CRUD operation to create the user, which handles password hashing
    user = crud_user.create_with_hashed_password(db=db_session, obj_in=user_in)
    return user

@pytest.fixture(scope="function")
def test_admin_user(db_session: Session) -> User:
    """
    Fixture to create and return a test administrator user in the database.
    This user has superuser privileges for testing admin-only endpoints.
    """
    admin_in = UserCreate(
        email="test_admin@example.com",
        password="adminpassword123",
        full_name="Test Admin",
        is_superuser=True # Mark as superuser
    )
    admin_user = crud_user.create_with_hashed_password(db=db_session, obj_in=admin_in)
    return admin_user


@pytest.fixture(scope="function")
def auth_headers(api_client: TestClient, test_user: User) -> dict:
    """
    Fixture to get authentication headers (JWT) for a regular test user.
    It logs in the `test_user` and extracts the access token.
    """
    # Directly create a token for the test user to avoid hitting the auth endpoint,
    # or if we want to explicitly test the auth endpoint:
    # login_data = {"username": test_user.email, "password": "testpassword123"}
    # response = api_client.post("/api/v1/auth/token", data=login_data)
    # token = response.json()["access_token"]
    
    # More robust way for auth_headers: directly create a valid token
    # This avoids dependency on the /token endpoint's correct functionality when testing other endpoints.
    token = create_access_token(data={"sub": test_user.email})
    headers = {"Authorization": f"Bearer {token}"}
    return headers

@pytest.fixture(scope="function")
def admin_auth_headers(api_client: TestClient, test_admin_user: User) -> dict:
    """
    Fixture to get authentication headers (JWT) for the test administrator user.
    """
    token = create_access_token(data={"sub": test_admin_user.email})
    headers = {"Authorization": f"Bearer {token}"}
    return headers


@pytest.fixture(scope="function")
def mock_object_storage_client():
    """
    Fixture to mock the ObjectStorageClient for tests.
    It uses `moto` to provide a local, in-memory mock of AWS S3
    and then wraps this with a MagicMock for the `ObjectStorageClient` interface.
    This avoids actual network calls to object storage during tests.
    """
    with mock_aws():
        # Setup mock S3 client provided by moto
        # Default region for moto is us-east-1, important for S3 bucket creation
        conn = boto3.client("s3", region_name="us-east-1")
        bucket_name = settings.OBJECT_STORAGE_BUCKET
        
        # Ensure the mock bucket exists for tests
        try:
            conn.create_bucket(Bucket=bucket_name)
        except conn.exceptions.BucketAlreadyOwnedByYou:
            pass # Bucket might already exist in the mock environment

        # Create a MagicMock object that simulates the ObjectStorageClient interface
        mock_client = MagicMock(spec=ObjectStorageClient)
        
        # Configure mock methods to interact with moto's S3, where applicable,
        # or return predefined values for simpler operations.
        # Note: For actual file content handling, you'd need to mock/stub S3 calls.
        mock_client.upload_file_from_local.side_effect = \
            lambda local_path, remote_path: conn.upload_file(Filename=local_path, Bucket=bucket_name, Key=remote_path)
        mock_client.download_file_to_local.side_effect = \
            lambda remote_path, local_path: conn.download_file(Bucket=bucket_name, Key=remote_path, Filename=local_path)
        
        # For presigned URLs, simply return dummy URLs as the actual generation isn't needed with mocks
        mock_client.generate_presigned_upload_url.return_value = "http://mock-presigned-upload-url.com/mock_file_upload"
        mock_client.generate_presigned_download_url.return_value = "http://mock-presigned-download-url.com/mock_file_download"
        
        # Simplified boolean return for existence and deletion checks
        mock_client.file_exists.return_value = True
        mock_client.delete_file.return_value = True

        # Override the dependency in FastAPI's dependency injection system
        def override_object_storage_client():
            return mock_client

        app.dependency_overrides[ObjectStorageClient] = override_object_storage_client
        
        yield mock_client

        # Clean up the dependency override after the test
        del app.dependency_overrides[ObjectStorageClient]

# Note: No explicit fixture for mocking the Rust engine is included here.
# For testing the Rust engine integration, you would typically:
# 1. Have integration tests in `tests/python/integration/test_worker_integration.py`
#    that call the actual Celery tasks which, in turn, call the PyO3 Rust functions.
# 2. Or, for unit testing Python code that calls Rust, use `unittest.mock.patch`
#    to mock the specific Rust function calls as needed within individual test files.
```