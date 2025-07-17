from fastapi import APIRouter
from http import HTTPStatus

router = APIRouter()

@router.get(
    "/health",
    summary="Check application health",
    response_description="Application health status",
    status_code=HTTPStatus.OK,
    tags=["Health"]
)
async def get_health_status():
    """
    Returns a simple status message to indicate that the application is running and responsive.
    This endpoint is typically used by load balancers, container orchestrators (like Kubernetes),
    and monitoring systems to perform liveness and readiness checks.
    """
    return {"status": "ok"}