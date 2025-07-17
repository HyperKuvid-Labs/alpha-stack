from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


async def get_db() -> AsyncGenerator[Session, None]:
    """
    Dependency to get a database session.
    Yields a SQLAlchemy session and ensures it's closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()