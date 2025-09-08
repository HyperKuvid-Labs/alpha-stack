import pytest
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

# --- Conditional Imports and Mocks ---
# These imports are essential for the fixtures to function correctly.
# If they fail (e.g., during a partial build or incomplete setup),
# mock objects are provided, and dependent fixtures will skip.

_HAS_SANCHAY_APP_MODULES = False
try:
    # Attempt to import core application components
    from src.sanchay_app.config import settings
    from src.sanchay_app.database.connection import SessionLocal, engine, Base
    # The Rust core crate 'sanchay_core' is expected to be built into the 'sanchay' Python package.
    import sanchay
    _HAS_SANCHAY_APP_MODULES = True
except ImportError as e:
    # Print a warning for easier debugging during development or CI setup
    print(f"WARNING: Could not import application modules for testing: {e}")
    print("Ensure 'src/sanchay_app' is in PYTHONPATH, and the 'sanchay' package (including Rust core) is built/installed.")

    # Define mock objects to prevent NameErrors in fixtures if imports fail
    class MockSettings:
        DATABASE_PATH = ":memory:" # Default to in-memory for mock DB operations
        LOG_LEVEL = "DEBUG"
    settings = MockSettings()

    class MockEngine:
        def connect(self): return self
        def begin(self): return self
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def execute(self, *args, **kwargs): return self
        def scalar(self, *args, **kwargs): return None
        def cursor(self): return self
        def close(self): pass
        def _get_dialect(self): return None # Needed for create_all/drop_all to function mock
    engine = MockEngine()

    class MockBase:
        # Provide mock metadata object with create_all and drop_all methods
        metadata = type('metadata', (object,), {
            'create_all': lambda self, bind: None,
            'drop_all': lambda self, bind: None
        })()
    Base = MockBase()

    class MockSession:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def close(self): pass
        def add(self, *args): pass
        def add_all(self, *args): pass
        def commit(self): pass
        def rollback(self): pass
        def query(self, *args): return self
        def filter(self, *args): return self
        def all(self): return []
        def first(self): return None
        def delete(self, *args): pass
    SessionLocal = lambda: MockSession()

    class MockSanchayRustCore:
        # Mock common functions expected from the Rust core
        def find_duplicates(self, path: str):
            print(f"Mock Rust core: find_duplicates called for {path}")
            return [{"path": f"{path}/dummy_dup1.txt", "hash": "abc"}, {"path": f"{path}/dummy_dup2.txt", "hash": "abc"}]
        def calculate_file_hash(self, path: str):
            print(f"Mock Rust core: calculate_file_hash called for {path}")
            return "dummy_hash"
        def process_directory(self, path: str):
            print(f"Mock Rust core: process_directory called for {path}")
            return {"total_files": 10, "processed_files": 10, "duration_ms": 100}

    sanchay = MockSanchayRustCore()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """
    Fixture to get the project root directory.
    Assumes conftest.py is located at `project-sanchay/tests/conftest.py`.
    """
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def temporary_database_path(project_root: Path) -> Path:
    """
    Creates a temporary SQLite database file for the entire test session.
    It patches the `DATABASE_PATH` environment variable and, if applicable,
    the `settings.DATABASE_PATH` attribute to ensure application components
    use this temporary database.
    """
    if not _HAS_SANCHAY_APP_MODULES:
        pytest.skip("Application modules not available, skipping database setup.")

    # Create a unique temporary directory to house the test database file
    temp_dir = tempfile.mkdtemp(prefix="sanchay_test_db_")
    db_file_path = Path(temp_dir) / "test.db"

    # Store original values to restore them after the session
    original_settings_db_path = None
    original_environ_db_path = os.environ.get("DATABASE_PATH")

    try:
        # Override the DATABASE_PATH environment variable
        os.environ["DATABASE_PATH"] = str(db_file_path)

        # If the settings module has already loaded and cached DATABASE_PATH, update it
        if hasattr(settings, 'DATABASE_PATH'):
            original_settings_db_path = settings.DATABASE_PATH
            settings.DATABASE_PATH = str(db_file_path)

        yield db_file_path
    finally:
        # Restore original settings and environment variables
        if original_settings_db_path is not None:
            settings.DATABASE_PATH = original_settings_db_path
        if original_environ_db_path is not None:
            os.environ["DATABASE_PATH"] = original_environ_db_path
        else:
            # If DATABASE_PATH wasn't set originally, remove it
            if "DATABASE_PATH" in os.environ:
                del os.environ["DATABASE_PATH"]

        # Clean up the temporary directory and its contents
        shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def db_session(temporary_database_path: Path):
    """
    Provides a SQLAlchemy session connected to a temporary SQLite database.
    Each test function gets a fresh database state (tables are dropped and recreated).
    """
    if not _HAS_SANCHAY_APP_MODULES:
        pytest.skip("Application modules not available, skipping database tests.")

    # The `engine` and `SessionLocal` from `src.sanchay_app.database.connection`
    # are expected to pick up the `DATABASE_PATH` from `os.environ` due to the
    # `temporary_database_path` fixture's setup.

    # Create all tables defined in the SQLAlchemy models for this test function
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        # Ensure the session is closed after the test
        session.close()
        # Drop all tables to ensure a clean slate for the next test function
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def sanchay_rust_core():
    """
    Provides access to the compiled Rust core extension module.
    Assumes the 'sanchay' Python package (containing the Rust module)
    is installed and available in the test environment.
    """
    if not _HAS_SANCHAY_APP_MODULES:
        pytest.skip("Application modules not available, skipping Rust core tests.")
    yield sanchay


@pytest.fixture(scope="function")
def app_config(temporary_database_path: Path):
    """
    Provides access to the application's configuration settings (`settings` object).
    Ensures that `DATABASE_PATH` within the settings reflects the temporary test database.
    This fixture ensures that tests can interact with a configured `settings` object
    that is isolated from the main application's configuration.
    """
    if not _HAS_SANCHAY_APP_MODULES:
        pytest.skip("Application modules not available, skipping config tests.")
    
    # The `temporary_database_path` fixture already handles patching `os.environ`
    # and `settings.DATABASE_PATH`. We yield the `settings` object which should
    # reflect these temporary changes for the duration of the test function.
    yield settings