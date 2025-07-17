import os
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from vegafs.database.session import AsyncSessionLocal
from vegafs.cache.config import get_redis_client_pool


# --- Database Dependencies ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an asynchronous SQLAlchemy database session.
    The session is created for each request and automatically closed after the request
    is finished, ensuring proper resource management.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            # In a production environment, use a proper logging framework here
            # e.g., logger.exception("Database session error")
            print(f"Database session error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred while processing the request."
            )


# --- Redis Dependencies ---

async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    Dependency to get an asynchronous Redis client from a shared connection pool.
    The client is yielded for use in route handlers.
    """
    try:
        redis_client = await get_redis_client_pool()
        yield redis_client
    except Exception as e:
        # In a production environment, use a proper logging framework here
        # e.g., logger.exception("Redis client error")
        print(f"Redis client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A caching service error occurred while processing the request."
        )


# --- Authentication/Authorization Dependencies ---

# Retrieve API Key from environment variables for security.
# In a production deployment, this should be loaded from a secrets management service.
VEGAFS_API_KEY = os.getenv("VEGAFS_API_KEY")

async def verify_api_key(
    api_key: str = Depends(
        HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or malformed API Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    )
) -> bool:
    """
    Dependency to verify a simple API key for access control.
    This is a basic implementation suitable for development or simple deployments.
    A production system would typically use JWTs or OAuth2 for more robust
    authentication and authorization, often involving user roles or permissions.
    """
    if VEGAFS_API_KEY is None:
        # This indicates a server configuration issue, not a client authentication failure.
        # In production, this should be an alertable error.
        print("CRITICAL ERROR: VEGAFS_API_KEY environment variable is not set.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Authentication key not set."
        )

    if api_key != VEGAFS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Invalid API Key.",
        )
    return True # Indicates successful authentication