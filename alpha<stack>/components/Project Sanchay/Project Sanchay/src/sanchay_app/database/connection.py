import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from .models import Base  # Assuming Base is defined in models.py and contains model declarations

logger = logging.getLogger(__name__)

# The database URL from our application configuration
DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine based on the DATABASE_URL.
# - `echo` parameter is controlled by settings, useful for debugging to see generated SQL.
# - For SQLite, `connect_args` can be used to pass arguments to the underlying `sqlite3.connect`.
#   `check_same_thread=False` is sometimes needed for multi-threaded access in SQLite,
#   but SQLAlchemy's connection pooling generally handles this for the Python layer.
#   We will rely on SQLAlchemy's default pooling behavior here.
# - For PostgreSQL (or other RDBMS), you might configure `pool_size`, `max_overflow`, etc.
#   These are less relevant for SQLite's single-file nature.
engine = create_engine(
    DATABASE_URL,
    echo=settings.DB_ECHO_SQL,
    # Example for SQLite specific argument if needed:
    # connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    # For production PostgreSQL, consider adding:
    # pool_size=10,  # Number of connections to keep in the pool
    # max_overflow=20, # Max additional connections beyond pool_size
)

# Create a configured "Session" class.
# - `autocommit=False` ensures that changes are part of a transaction and need to be explicitly committed.
# - `autoflush=False` prevents the session from flushing pending changes to the database automatically
#   before every query, giving more control over when data is written.
# - `bind=engine` links this sessionmaker to our database engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Provides a context manager for handling a database session.
    This ensures that the session is properly closed and transactions are
    committed or rolled back automatically.

    Usage:
        with get_db() as db:
            # Perform database operations using 'db' session
            user = db.query(User).filter_by(id=1).first()
            if user:
                user.name = "New Name"
            db.add(user) # Not strictly needed if object is already tracked
        # Session is committed if no exceptions, or rolled back and closed if exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit the transaction if everything was successful
    except Exception as e:
        logger.error(f"Database transaction failed: {e}", exc_info=True)
        db.rollback()  # Rollback changes on any exception
        raise  # Re-raise the exception after rollback
    finally:
        db.close()  # Ensure the session is always closed

def initialize_database():
    """
    Creates all database tables defined by SQLAlchemy models if they do not already exist.
    This function should be called once during the application's startup phase
    (e.g., in `sanchay_app.__main__.py`).
    """
    logger.info(f"Attempting to initialize database tables at: {DATABASE_URL}")
    try:
        # Base.metadata.create_all requires that all ORM models inheriting from `Base`
        # have been imported and registered with Base.metadata.
        # This is implicitly handled by `from .models import Base` and subsequent imports
        # within `models.py` or other modules that define models.
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully (if they didn't exist).")
    except Exception as e:
        logger.critical(f"FATAL: Error initializing database tables: {e}", exc_info=True)
        raise  # Re-raise to halt application startup if critical database init fails