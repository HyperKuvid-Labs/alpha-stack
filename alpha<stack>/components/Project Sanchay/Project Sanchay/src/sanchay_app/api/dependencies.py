from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from config.settings import Settings, get_app_settings
from src.sanchay_app.database.connection import get_session_local


def get_settings() -> Settings:
    """
    Dependency function that provides the application's configuration settings.
    This ensures that settings are loaded once and consistently used across API endpoints.
    """
    return get_app_settings()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a SQLAlchemy database session to API endpoints.
    It manages the lifecycle of the database session, ensuring it is properly
    closed after the request has been processed, even if errors occur.
    """
    db = get_session_local()
    try:
        yield db
    finally:
        db.close()