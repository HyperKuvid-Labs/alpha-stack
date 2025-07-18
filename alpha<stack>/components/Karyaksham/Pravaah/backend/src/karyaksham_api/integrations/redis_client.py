import redis.asyncio as redis
from redis.asyncio import Redis
from karyaksham_api.core.config import settings

# A module-level variable to hold the Redis client instance.
# This allows for a "singleton-like" access pattern within the application's lifespan.
_redis_client: Redis | None = None

async def initialize_redis_client() -> None:
    """
    Initializes the global asynchronous Redis client instance.
    This function should be called once during the application's startup phase
    (e.g., within FastAPI's lifespan event).
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            encoding="utf-8",        # Ensures consistent encoding for keys/values
            decode_responses=True,    # Automatically decodes responses to Python strings
        )

async def get_redis_client() -> Redis:
    """
    Returns the initialized asynchronous Redis client instance.
    This function is intended to be used as a dependency in FastAPI routes or other
    application components that require access to Redis.

    Raises:
        RuntimeError: If the Redis client has not been initialized via
                      `initialize_redis_client()` prior to being called.
    """
    if _redis_client is None:
        # This indicates a critical application setup error.
        raise RuntimeError("Redis client has not been initialized. "
                           "Ensure initialize_redis_client() is called during startup.")
    return _redis_client

async def close_redis_client() -> None:
    """
    Closes the global Redis client connection.
    This function should be called once during the application's shutdown phase
    (e.g., within FastAPI's lifespan event).
    """
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None # Reset the client to None after closing