import os
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer


# --- Configuration ---
# It's crucial to load these values from environment variables in production.
# The default values provided here are ONLY for development and should be overridden.
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-for-development-only-change-this")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# --- Password Hashing ---
# CryptContext configures the password hashing algorithm. bcrypt is a strong,
# widely recommended algorithm. `deprecated="auto"` handles upgrading old hashes.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against its hashed version.

    Args:
        plain_password: The password provided by the user.
        hashed_password: The hashed password stored in the database.

    Returns:
        True if passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using the configured algorithm.

    Args:
        password: The plain-text password to hash.

    Returns:
        The hashed password string.
    """
    return pwd_context.hash(password)

# --- JWT Token Management ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.

    Args:
        data: A dictionary containing the payload to be encoded in the token.
              Typically includes user identifiers like `sub` (subject/username) or `user_id`.
        expires_delta: Optional timedelta object specifying the token's validity duration.
                       If None, `ACCESS_TOKEN_EXPIRE_MINUTES` is used.

    Returns:
        The encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire}) # Add expiration timestamp to the payload
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """
    Decodes and verifies a JWT access token.

    Args:
        token: The JWT string received from the client.

    Returns:
        The decoded payload as a dictionary if the token is valid and not expired.

    Raises:
        HTTPException: If the token is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        # Catch specific JWT errors and raise an HTTPException for FastAPI to handle
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- FastAPI Dependency for Authentication ---
# OAuth2PasswordBearer is a FastAPI utility to extract the token from the Authorization header.
# The tokenUrl specifies the endpoint where clients can obtain a token (e.g., login endpoint).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token") # Placeholder, adjust as per API design

async def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency function to validate the access token and retrieve its payload.
    This function can be used in FastAPI route decorators to secure endpoints.

    Args:
        token: The JWT string extracted by OAuth2PasswordBearer from the request header.

    Returns:
        The decoded payload of the authenticated user's token.

    Raises:
        HTTPException: If the token is invalid or authentication fails.
    """
    # The decode_access_token function already handles raising HTTPException on failure
    payload = decode_access_token(token)

    # In a full application, you would typically fetch user details from a database
    # based on the `user_id` or `sub` claim in the payload to return a rich User object.
    # Example:
    # user_id = payload.get("user_id")
    # if not user_id:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token payload")
    # user = await get_user_from_db_by_id(user_id) # Requires an async DB operation
    # if user is None:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # return user

    # For this file's scope, we return the payload directly.
    return payload
<ctrl63>