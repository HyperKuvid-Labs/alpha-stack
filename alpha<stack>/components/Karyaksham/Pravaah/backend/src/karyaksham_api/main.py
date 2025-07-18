import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from karyaksham_api.api.v1.api import api_router
from karyaksham_api.core.config import settings
from karyaksham_api.db.session import close_db_session_factory, init_db_session_factory
from karyaksham_api.integrations.redis_client import close_redis_client, init_redis_client

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown events.
    Initializes database and Redis connections, then closes them on shutdown.
    """
    logger.info("Application startup begins...")
    try:
        # Initialize database connection pool
        await init_db_session_factory()
        logger.info("Database connection pool initialized.")

        # Initialize Redis client
        await init_redis_client()
        logger.info("Redis client initialized.")

    except Exception as e:
        logger.critical(f"Failed to initialize application dependencies: {e}", exc_info=True)
        # Depending on the severity, you might want to raise an exception here
        # or implement a more robust health check and graceful degradation.
        raise

    yield  # Application runs here

    logger.info("Application shutdown begins...")
    try:
        # Close Redis client
        await close_redis_client()
        logger.info("Redis client closed.")

        # Close database connection pool
        await close_db_session_factory()
        logger.info("Database connection pool closed.")

    except Exception as e:
        logger.error(f"Error during application shutdown: {e}", exc_info=True)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

# Set up CORS middleware
# Ensure settings.BACKEND_CORS_ORIGINS is correctly configured
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
        allow_headers=["*"],  # Allows all headers
    )
    logger.info(f"CORS enabled for origins: {settings.BACKEND_CORS_ORIGINS}")
else:
    logger.warning("CORS is not explicitly configured. It might be disabled or rely on default behavior.")


# Include API routers
app.include_router(api_router, prefix=settings.API_V1_STR)
logger.info(f"API routers included with prefix: {settings.API_V1_STR}")

# Mount static files (e.g., favicon)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Static files mounted from: {STATIC_DIR}")
else:
    logger.warning(f"Static directory not found at: {STATIC_DIR}. Static files will not be served.")


@app.get("/")
async def root():
    """
    Root endpoint for basic health check or redirect to docs.
    """
    return {"message": f"{settings.PROJECT_NAME} API is running!", "docs": f"{settings.API_V1_STR}/docs"}