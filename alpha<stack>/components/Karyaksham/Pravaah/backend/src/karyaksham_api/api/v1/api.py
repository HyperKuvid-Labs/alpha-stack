from fastapi import APIRouter

from karyaksham_api.api.v1.endpoints import auth
from karyaksham_api.api.v1.endpoints import jobs
from karyaksham_api.api.v1.endpoints import users


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])