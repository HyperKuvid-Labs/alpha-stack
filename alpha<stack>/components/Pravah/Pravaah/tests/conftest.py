import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.models.base import Base
# Import all ORM models here to ensure they are registered with Base.metadata
from app.db.models import job, user 
from app.api.v1.dependencies import get_db, get_current_user
from app.api.v1.schemas import UserRead
import os

# --- Database Fixtures ---

@pytest.fixture(scope="session")
def test_engine():
    """
    Creates an in-memory SQLite database engine for the entire test session.
    All SQLAlchemy models defined in `app/db/models` are created on this engine.
    This provides a clean database schema for testing.
    """
    # Use an in-memory SQLite database for fast and isolated tests.
    # The 'check_same_thread=False' is needed for SQLite to work with multiple threads/async.
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        # pool_pre_ping=True # Optional: for persistent connections, not strictly needed for in-memory
    )
    
    # Create all tables defined in Base.metadata for the test database
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Drop all tables after the test session completes to clean up
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Provides a SQLAlchemy session for each test function.
    Each test gets a fresh, isolated session with a transaction.
    Changes made by a test are rolled back after the test completes,
    ensuring a clean state for the next test.
    """
    connection = test_engine.connect()
    # Begin a transaction for the test, ensuring isolation
    transaction = connection.begin()
    
    # Create a new session bound to the connection
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()
    
    # Yield the session to the test function
    yield session

    # After the test, roll back the transaction to discard any changes
    transaction.rollback()
    session.close()
    connection.close()


@pytest.fixture(scope="function")
def override_get_db(db_session):
    """
    Pytest fixture to override FastAPI's `get_db` dependency.
    This ensures that API endpoints called during tests use the `db_session` fixture,
    connecting to the test database instead of the production database.
    """
    def _override_get_db():
        yield db_session
    return _override_get_db


# --- Authentication Fixtures ---

@pytest.fixture(scope="function")
def test_user():
    """
    Provides a dummy `UserRead` object representing a standard authenticated user.
    Useful for testing API endpoints that require authentication but not specific roles.
    """
    return UserRead(id=1, email="testuser@example.com", is_active=True, is_admin=False)


@pytest.fixture(scope="function")
def test_admin_user():
    """
    Provides a dummy `UserRead` object representing an authenticated administrator.
    Useful for testing API endpoints that require admin privileges.
    """
    return UserRead(id=99, email="admin@example.com", is_active=True, is_admin=True)


@pytest.fixture(scope="function")
def override_get_current_user(test_user):
    """
    Pytest fixture to override FastAPI's `get_current_user` dependency.
    By default, it provides the `test_user` (non-admin).
    This can be parameterized or overridden in specific tests for different user types.
    """
    def _override_get_current_user():
        yield test_user
    return _override_get_current_user


@pytest.fixture(scope="function")
def override_get_current_admin_user(test_admin_user):
    """
    Pytest fixture to override FastAPI's `get_current_user` dependency to specifically
    provide an admin user. Useful for testing routes protected by admin roles.
    """
    def _override_get_current_admin_user():
        yield test_admin_user
    return _override_get_current_admin_user


# --- FastAPI Test Client Fixture ---

@pytest.fixture(scope="function")
def client(override_get_db, override_get_current_user):
    """
    Provides a FastAPI `TestClient` instance for making requests to the application.
    This client is configured to use the test database and a default (non-admin)
    authenticated user by overriding `get_db` and `get_current_user` dependencies.
    """
    # Override database dependency
    app.dependency_overrides[get_db] = override_get_db
    # Override authentication dependency with a standard test user
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up dependency overrides after the test function finishes
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_client(override_get_db, override_get_current_admin_user):
    """
    Provides a FastAPI `TestClient` instance configured for an admin user.
    Useful for testing API endpoints that require administrator privileges.
    """
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_admin_user

    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# --- Rust Core Interface Note ---
# For integration tests involving the Rust core (`pravah_core`), it is crucial
# that the Rust library is built as a Python wheel and installed in the test environment.
# This is typically handled by the project's build system (e.g., `maturin develop`
# or `pip install` a built wheel) as part of the CI/CD pipeline or local setup script.
# Directly building it within conftest.py is generally not recommended due to:
# 1. Performance overhead (rebuilding for every test session).
# 2. Dependency management (requiring `maturin` to be installed and in PATH for tests).

# A fixture like the one below can act as a check or a reminder, but direct build
# should ideally happen outside the test execution phase.
@pytest.fixture(scope="session", autouse=True)
def check_rust_core_availability():
    """
    Checks if the Rust core `pravah_core` module is importable.
    This fixture runs once per test session.
    It does NOT build the module, but merely verifies its presence,
    alerting if integration tests might fail due to a missing core.
    """
    try:
        import pravah_core
        # You could also try calling a simple function from pravah_core to ensure it's callable
        # e.g., pravah_core.version() if such a function exists
        print("\nPyO3 Rust core 'pravah_core' is successfully imported and available.")
    except ImportError:
        pytest.skip(
            "Rust core 'pravah_core' not found. "
            "Skipping tests that rely on the Rust engine. "
            "Ensure it is built and installed (`maturin develop` in `pravah_core/`)."
        )
    except Exception as e:
        pytest.fail(f"Error importing Rust core 'pravah_core': {e}. "
                    "Check Rust build and PyO3 bindings.")
    yield

# Example of a mock for the Rust core (to be used in specific unit tests)
# This is typically done using `unittest.mock.patch` directly in the test file,
# but `conftest.py` could provide a helper if mocking logic is complex and reused.
# @pytest.fixture
# def mock_rust_processor(mocker):
#     """
#     Provides a mock for the Pravah Rust core processing engine.
#     """
#     # Assuming app.core.processor.py has a function like `process_files`
#     mock_processor = mocker.patch("app.core.processor.PravahRustProcessor", autospec=True)
#     mock_instance = mock_processor.return_value
#     mock_instance.process_files.return_value = {"status": "mocked_success", "processed_count": 0}
#     return mock_instance