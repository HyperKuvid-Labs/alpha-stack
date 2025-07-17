import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.users import router as users_router
from app.utils.logging import setup_logging
from app.db.session import init_db_session, close_db_session

# Load application settings from environment variables or .env file
settings = get_settings()

# Configure structured logging for the application
setup_logging(log_level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Pravah: High-Performance File & Data Processing Engine. "
                "The core engine is built in Rust for optimal performance.",
    version=settings.VERSION,
    docs_url="/api/docs",          # Swagger UI documentation endpoint
    redoc_url="/api/redoc",        # ReDoc documentation endpoint
    openapi_url="/api/openapi.json", # OpenAPI specification endpoint
)

# Configure CORS (Cross-Origin Resource Sharing) middleware
# This allows frontend applications served from different origins to interact with the API.
# In production, `allow_origins` should be restricted to known frontend URLs for security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # List of allowed origins (e.g., ["http://localhost:3000"])
    allow_credentials=True,               # Allow cookies and authentication headers to be sent
    allow_methods=["*"],                  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],                  # Allow all HTTP headers
)

# Include API routers from app/api/v1/endpoints
# Each router groups related endpoints (e.g., /jobs, /users, /health)
app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])
app.include_router(users_router, prefix="/api/v1", tags=["Users"])

@app.on_event("startup")
async def startup_event():
    """
    Event handler that runs when the FastAPI application starts up.
    It's used to initialize global resources, such as database connections.
    """
    logger.info("Starting Pravah application...")
    try:
        await init_db_session()
        logger.info("Database session initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database session: {e}", exc_info=True)
        # Depending on criticality, you might want to raise the exception or exit here

    # Additional startup tasks can be added here, e.g.:
    # - Initialize connections to other external services (S3, message queues).
    # - Perform a warm-up call to the Rust core engine if it has significant cold-start overhead.
    logger.info("Pravah application startup complete.")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Event handler that runs when the FastAPI application shuts down.
    It's used to gracefully clean up resources, such as closing database connections.
    """
    logger.info("Shutting down Pravah application...")
    try:
        await close_db_session()
        logger.info("Database session closed successfully.")
    except Exception as e:
        logger.error(f"Failed to close database session: {e}", exc_info=True)

    # Additional shutdown tasks can be added here, e.g.:
    # - Gracefully close connections to external services.
    # - Flush any remaining logs.
    logger.info("Pravah application shutdown complete.")

# If this file is run directly (e.g., `python main.py` or `uvicorn main:app`),
# uvicorn is typically used from the command line for production.
# This block is useful for local development or simple testing.
if __name__ == "__main__":
    import uvicorn
    # Make sure to set environment variables or have a .env file for local run
    uvicorn.run(app, host="0.0.0.0", port=settings.APP_PORT)