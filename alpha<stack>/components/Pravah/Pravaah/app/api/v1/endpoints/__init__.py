from fastapi import APIRouter

# Import routers from individual endpoint files
# Assuming each file exports its APIRouter instance as 'router'
from .health import router as health_router
from .jobs import router as jobs_router
from .users import router as users_router

# Create a main router that aggregates all specific endpoint routers
# This router will then be included in the main v1 router (e.g., in app/api/v1/__init__.py)
# No prefix is applied here; the /v1 prefix will be applied by the parent router in the API versioning layer.
all_endpoints_router = APIRouter()

# Include individual routers into the aggregate router
all_endpoints_router.include_router(health_router)
all_endpoints_router.include_router(jobs_router)
all_endpoints_router.include_router(users_router)