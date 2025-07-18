from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from karyaksham_api.core.config import settings

# Construct the database URL from settings
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
# pool_pre_ping=True ensures that connections in the pool are tested before use,
# helping to prevent issues with stale connections, which is good for production.
# future=True enables 2.0-style usage, which is recommended for new projects.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

# Create a SessionLocal class
# autocommit=False means that changes are not automatically committed to the database.
# autoflush=False means that changes are not automatically flushed to the database before query operations.
# bind=engine connects the session to our database engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for declarative models
# All SQLAlchemy models (e.g., User, Job) will inherit from this Base.
# This is used by Alembic for migrations as well.
Base = declarative_base()

# Dependency to get a database session for FastAPI routes
def get_db():
    """
    Provides a SQLAlchemy database session to FastAPI endpoints.
    This function yields a session, ensuring it's properly closed
    after the request is processed, regardless of success or failure.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()