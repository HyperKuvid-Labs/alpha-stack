from fastapi import APIRouter

# Import routers from different API versions or logical groupings
# As per the project structure, 'v1' is an API version subdirectory,
# and 'jobs.py' is expected to contain a router for job-related endpoints.
from .v1.jobs import router as v1_jobs_router

# Create a main APIRouter instance for the 'api' package.
# This router will aggregate all specific API version routers.
api_router = APIRouter()

# Include the v1 jobs router with its specific prefix and tags.
# The prefix ensures all endpoints from v1_jobs_router will be under /v1.
# Tags help categorize endpoints in the OpenAPI documentation (Swagger UI).
api_router.include_router(v1_jobs_router, prefix="/v1", tags=["jobs", "v1"])

# As the API evolves, additional version routers (e.g., v2, v3) or
# routers for other functional areas can be included here following a similar pattern.
# Example:
# from .v1.files import router as v1_files_router
# api_router.include_router(v1_files_router, prefix="/v1", tags=["files", "v1"])

# This 'api_router' will then be included in the main FastAPI application
# (likely in app/main.py) to expose all defined API endpoints.