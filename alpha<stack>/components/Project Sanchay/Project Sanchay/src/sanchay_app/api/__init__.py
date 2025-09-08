from fastapi import APIRouter

# Create the main API router for the version 1 API endpoints.
# This router acts as a top-level container for all specific resource routers
# defined within the `api` package (e.g., for jobs, status, etc.).
# It defines a common prefix for all endpoints in this version.
v1_router = APIRouter(prefix="/api/v1")

# Import and include specific resource routers from other modules within this package.
# This modular approach keeps routes organized and maintainable.

# Example: Include the router for job-related endpoints.
# It is expected that `routes.py` defines an APIRouter instance named `jobs_router`.
from .routes import jobs_router
v1_router.include_router(jobs_router)

# Future: As more API resources are added, they can be imported and included here:
# from .routes import users_router
# v1_router.include_router(users_router)
# from .routes import settings_router
# v1_router.include_router(settings_router)

# The `v1_router` can now be imported by the main FastAPI application instance
# (e.g., in `sanchay_app/__main__.py` or a dedicated `server.py`) and mounted.
# Example: `app.include_router(v1_router)`