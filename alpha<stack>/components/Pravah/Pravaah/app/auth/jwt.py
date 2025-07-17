from datetime import datetime, timedelta, timezone
from typing import List, Optional

from jose import JWTError, jwt
from pydantic import BaseModel

from fastapi import HTTPException, status

from config.settings import settings

# Algorithm used for JWT encoding/decoding
ALGORITHM = "HS256"

class Token(BaseModel):
    """Represents the JWT token itself."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """
    Represents the decoded payload data from a JWT.
    Fields correspond to expected claims in the token.
    """
    user_id: int
    username: str
    roles: List[str] = []
    sub: Optional[str] = None # Standard JWT subject claim, typically user_id or username string

def create_access_token(user_id: int, username: str, roles: List[str]) -> str:
    """
    Creates a new JWT access token for a given user.

    Args:
        user_id (int): The unique identifier of the user.
        username (str): The username of the user.
        roles (List[str]): A list of roles assigned to the user.

    Returns:
        str: The encoded JWT access token.
    """
    to_encode = {
        "user_id": user_id,
        "username": username,
        "roles": roles,
        "sub": str(user_id) # 'sub' claim should be a string identifier, often the user ID
    }

    # Set expiration time
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    to_encode.update({"iat": datetime.now(timezone.utc)}) # Issued at

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> TokenData:
    """
    Verifies a JWT token and returns its decoded payload as TokenData.

    Args:
        token (str): The JWT token string.

    Returns:
        TokenData: The validated token data containing user_id, username, and roles.

    Raises:
        HTTPException: If the token is invalid (e.g., malformed, expired, invalid signature)
                       or if required claims are missing.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        # Extract required claims and validate their types
        user_id = payload.get("user_id")
        username = payload.get("username")
        roles = payload.get("roles") # Get raw roles
        sub = payload.get("sub")

        # Basic validation for critical claims
        if not (isinstance(user_id, (int, float)) and isinstance(username, str) and isinstance(roles, list) and isinstance(sub, str)):
            raise credentials_exception # Token is malformed or missing critical claims

        # Ensure user_id is an integer, handling float case if JSON parser converts it
        if isinstance(user_id, float):
            user_id = int(user_id)

        # Create and return TokenData object
        token_data = TokenData(user_id=user_id, username=username, roles=roles, sub=sub)
        return token_data

    except JWTError as e:
        # Catches various JWT errors like ExpiredSignatureError, InvalidSignatureError, DecodeError
        detail = "Invalid token"
        if isinstance(e, jwt.ExpiredSignatureError):
            detail = "Token has expired"
        elif isinstance(e, jwt.InvalidTokenError):
            detail = f"Invalid token signature or format: {e}"
        # Catching DecodeError explicitly for clarity, though InvalidTokenError often covers it
        elif isinstance(e, jwt.DecodeError):
            detail = f"Token decode error: {e}"
        else:
            detail = f"JWT validation error: {e}"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Catch any other unexpected errors during token processing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during token validation: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )