import logging

from fastapi import FastAPI, status
from fastapi.responses import PlainTextResponse
from redis.asyncio import Redis

from vegafs.config import settings
from vegafs.database import engine # This engine needs to be an AsyncEngine
from vegafs.redis_client import redis_client as global_redis_client # Alias to avoid name clashes
from vegafs.api.v1 import jobs

# Configure logging for the application
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="VēgaFS: High-Performance File & Data Processing Engine API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include API routers
app.include_router(jobs.router, prefix="/api/v1", tags=["Job Management"])

@app.get("/health", response_class=PlainTextResponse, status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    """
    Checks the health status of the API and its core dependencies.
    This endpoint can be used by load balancers and container orchestrators.
    """
    # Check database connection
    try:
        # Pinging the database is not directly supported by SQLAlchemy engine itself.
        # Instead, we can try to get a connection from the pool.
        async with engine.connect() as connection:
            # Execute a simple query to ensure the connection is active
            await connection.scalar("SELECT 1")
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_healthy = False

    # Check Redis connection
    redis_healthy = False
    try:
        if global_redis_client:
            await global_redis_client.ping()
            redis_healthy = True
        else:
            logger.warning("Redis client not initialized yet.")
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_healthy = False

    # A simple indicator for Rust core. True if Python app is running and import worked.
    # More advanced checks might involve calling a dummy Rust function.
    rust_core_healthy = True # Assumed healthy if the app started without PyO3 import errors

    if db_healthy and redis_healthy and rust_core_healthy:
        return "OK"
    else:
        # Return 503 Service Unavailable if any critical dependency is unhealthy
        response_content = "Service Unavailable:\n"
        if not db_healthy:
            response_content += "- Database connection failed\n"
        if not redis_healthy:
            response_content += "- Redis connection failed\n"
        if not rust_core_healthy:
            response_content += "- Rust core not responding (unlikely if app started)\n"
        logger.error(f"Health check failed: {response_content.strip()}")
        return PlainTextResponse(response_content, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    Initializes database and Redis connections.
    """
    logger.info(f"Starting up {settings.APP_NAME} v{settings.APP_VERSION} application...")
    try:
        # The SQLAlchemy async engine is created when `vegafs.database` is imported.
        # We can perform a connection test here.
        async with engine.connect() as connection:
            # This implicitly tests the connection pool initialization
            logger.info("Database connection pool initialized and tested successfully.")

        # Initialize the global Redis client instance
        global global_redis_client # Indicate that we're modifying the global variable
        global_redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await global_redis_client.ping() # Test connection to Redis
        logger.info("Redis client connected and tested successfully.")

        # The Rust core via PyO3 is loaded implicitly when its module is first imported.
        # If there were any issues, it would likely raise an ImportError during application startup.
        logger.info("VēgaFS Rust core implicitly loaded via PyO3 bindings.")

    except Exception as e:
        logger.exception(f"Critical error during application startup: {e}")
        # In a production environment, you might want to re-raise the exception
        # or exit the application if critical dependencies cannot be met.
        # For now, we log and allow the app to start, relying on /health to indicate issues.


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    Closes database and Redis connections.
    """
    logger.info(f"Shutting down {settings.APP_NAME} application...")
    try:
        # Dispose of the SQLAlchemy database engine (closes all connections in the pool)
        await engine.dispose()
        logger.info("Database connection pool disposed.")

        # Close the Redis client connection
        if global_redis_client:
            await global_redis_client.close()
            logger.info("Redis client connection closed.")

    except Exception as e:
        logger.exception(f"Error during application shutdown: {e}")