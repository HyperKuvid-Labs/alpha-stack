from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from karyaksham_api.auth.jwt import decode_access_token
from karyaksham_api.crud.crud_user import user as crud_user
from karyaksham_api.db.models.user import User as DBUser, UserRole
from karyaksham_api.db.session import get_async_session
from karyaksham_api.schemas.token import TokenData

# Password Hashing Configuration
# Using bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer for extracting token from Authorization header
# tokenUrl specifies the URL where the client can obtain a token (e.g., login endpoint)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using the configured password context.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    Returns True if they match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)

async def get_current_user(
    db: AsyncSession = Depends(get_async_session), token: str = Depends(oauth2_scheme)
) -> DBUser:
    """
    FastAPI dependency to retrieve the current authenticated user based on a JWT token.
    Raises HTTPException if the token is invalid or the user does not exist.

    Args:
        db: The asynchronous database session dependency.
        token: The JWT token extracted from the Authorization header.

    Returns:
        The authenticated database User object.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the token using the logic from jwt.py
        token_data: TokenData = decode_access_token(token)
        if token_data.sub is None:
            raise credentials_exception
    except Exception: # Catch JWTError from jose or other decoding issues
        raise credentials_exception

    # Retrieve the user from the database using the subject (user ID) from the token
    user = await crud_user.get(db, id=int(token_data.sub)) # Assuming token.sub is user ID (int)
    if not user:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    FastAPI dependency to ensure the current authenticated user is active.
    Raises HTTPException if the user's 'is_active' status is False.

    Args:
        current_user: The authenticated user obtained from get_current_user dependency.

    Returns:
        The active authenticated database User object.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

def get_current_user_with_roles(allowed_roles: List[UserRole]):
    """
    FastAPI dependency factory that checks if the current authenticated user
    has one of the specified allowed roles.

    This function returns another async dependency function, which is then used
    in FastAPI route decorators.

    Args:
        allowed_roles: A list of UserRole enums that are permitted to access the endpoint.

    Returns:
        An async dependency function that verifies the user's role.
    """
    async def role_checker(current_user: DBUser = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    return role_checker

# Example of how specific role dependencies can be defined:
# get_current_admin_user = get_current_user_with_roles([UserRole.ADMIN])
# get_current_manager_user = get_current_user_with_roles([UserRole.ADMIN, UserRole.MANAGER])