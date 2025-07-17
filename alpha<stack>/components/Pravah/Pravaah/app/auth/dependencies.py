from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.user import User
from app.auth import jwt
from app.auth.rbac import Role
from config.settings import settings


# OAuth2PasswordBearer to expect a Bearer token in the Authorization header.
# The tokenUrl specifies the endpoint where clients can obtain a token (e.g., login).
# This aligns with the external REST API definition for authentication.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"v1/auth/token")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Dependency that decodes the JWT token from the Authorization header,
    validates it, and fetches the corresponding user from the database.
    Raises HTTPException for invalid tokens or non-existent users.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.verify_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:  # Specific JWT decoding/validation errors
        raise credentials_exception
    except Exception:  # Catch any other unexpected errors during token verification
        raise credentials_exception

    # Fetch user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        # If user ID from token does not exist in DB, it's a credential issue
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Dependency that ensures the authenticated user is active.
    Raises HTTPException if the user is not active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


class RoleChecker:
    """
    A callable class to create a FastAPI dependency for role-based access control.
    It takes a list of allowed `Role` enums and checks if the current user
    has at least one of these roles.

    Usage: Depends(RoleChecker([Role.ADMIN, Role.MANAGER]))
    """
    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Annotated[User, Depends(get_current_active_user)]) -> User:
        """
        Executes the role check. Requires an active user.
        """
        # Convert user's roles and allowed roles to sets of their string names for efficient checking
        user_roles_names = {role_obj.name for role_obj in current_user.roles} # Assuming current_user.roles is a list of Role ORM objects
        allowed_roles_names = {role.name for role in self.allowed_roles}

        # Check if there is any intersection between the user's roles and the allowed roles
        if not (user_roles_names.intersection(allowed_roles_names)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user