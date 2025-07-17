from enum import Enum
from typing import List

from fastapi import Depends, HTTPException, status
from app.db.models.user import User
from app.auth.dependencies import get_current_active_user


class UserRole(str, Enum):
    """
    Defines the roles available to users in the application.
    """
    ADMIN = "admin"
    USER = "user"
    # Add more specific roles as needed, e.g., 'DATA_SCIENTIST', 'DEV_OPS'


class RoleChecker:
    """
    A FastAPI dependency class to enforce Role-Based Access Control (RBAC) on API endpoints.
    It checks if the current authenticated user's role is among the allowed roles for a given endpoint.
    """
    def __init__(self, allowed_roles: List[UserRole]):
        """
        Initializes the RoleChecker with a list of roles that are permitted to access the resource.

        Args:
            allowed_roles (List[UserRole]): A list of UserRole enums that are authorized.
        """
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_active_user)):
        """
        The FastAPI dependency function that performs the role check.
        It is an async function because `get_current_active_user` might be async.

        Args:
            current_user (User): The authenticated user object, obtained from
                                 the `get_current_active_user` dependency.

        Raises:
            HTTPException: If the current user's role is not in the allowed_roles,
                           a 403 Forbidden error is raised.

        Returns:
            User: The current_user object if authorization is successful.
        """
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required roles: {', '.join(self.allowed_roles)}"
            )
        return current_user

# Helper functions for common role checks (optional, but improves readability in endpoint definitions)

def require_admin():
    """
    FastAPI dependency to ensure the user has the 'admin' role.
    Usage: `Depends(require_admin())`
    """
    return RoleChecker([UserRole.ADMIN])

def require_user_or_admin():
    """
    FastAPI dependency to ensure the user has either 'user' or 'admin' role.
    Usage: `Depends(require_user_or_admin())`
    """
    return RoleChecker([UserRole.USER, UserRole.ADMIN])

# Example of how to use these in `app/api/v1/endpoints/*.py` (not part of this file):
#
# from fastapi import APIRouter, Depends
# from app.auth.rbac import require_admin, require_user_or_admin, UserRole # Import UserRole if needed for typing
# from app.db.models.user import User # To hint the current_user type if returned
#
# router = APIRouter()
#
# @router.get("/some_resource", response_model=SomeSchema, dependencies=[Depends(require_user_or_admin())])
# async def get_some_resource(current_user: User = Depends(require_user_or_admin)):
#     # This endpoint is accessible by users with 'user' or 'admin' roles.
#     # current_user will contain the User object if authorized.
#     return {"message": f"Hello, {current_user.username}! Here is your resource."}
#
# @router.post("/admin_action", status_code=status.HTTP_200_OK, dependencies=[Depends(require_admin())])
# async def perform_admin_action():
#     # This endpoint is only accessible by users with the 'admin' role.
#     return {"status": "Admin action performed successfully."}