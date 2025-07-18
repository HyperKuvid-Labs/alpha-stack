```python
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from fastapi import HTTPException, status

from karyaksham_api.core.config import settings
from karyaksham_api.schemas.token import TokenData # Assuming TokenData is defined to hold username/sub


# JWT configuration constants
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"  # Standard algorithm for symmetric key signing (HMAC-SHA256)
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Ensure SECRET_KEY is loaded; crucial for security
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set. JWT authentication cannot be performed.")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.

    Args:
        data (dict): The payload data to encode into the token.
                     Must include a 'sub' (subject) key for the user identifier.
        expires_delta (Optional[timedelta]): Optional timedelta for token expiration.
                                             If None, uses ACCESS_TOKEN_EXPIRE_MINUTES from settings.

    Returns:
        str: The encoded JWT access token.

    Raises:
        ValueError: If 'sub' is missing from the provided data.
    """
    to_encode = data.copy()

    # Ensure 'sub' is present in the data for consistency and user identification
    if "sub" not in to_encode:
        raise ValueError("Payload data must contain 'sub' (subject) for the user identifier.")

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception: HTTPException) -> TokenData:
    """
    Verifies a JWT token and extracts its payload.

    Args:
        token (str): The JWT token string to verify.
        credentials_exception (HTTPException): The exception to raise if token
                                               verification fails. This should typically
                                               be an HTTPException with status.HTTP_401_UNAUTHORIZED.

    Returns:
        TokenData: An object representing the token's payload data (e.g., user ID).

    Raises:
        HTTPException: If the token is invalid (e.g., malformed, expired, invalid signature)
                       or if the required subject ('sub') is missing from the payload.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            # Token does not contain a subject ('sub') which is essential for identifying the user
            raise credentials_exception
        
        # Assuming TokenData schema only needs 'username' for now based on common JWT usage.
        # If your TokenData also has 'scopes' or other fields, retrieve them from payload here:
        # scopes: Optional[list[str]] = payload.get("scopes", [])
        # token_data = TokenData(username=username, scopes=scopes)
        token_data = TokenData(username=username)

    except JWTError:
        # This catches various JWT-related errors, such as:
        # - Invalid signature (token was tampered with)
        # - Expired token
        # - Invalid audience/issuer (if configured in decode options)
        raise credentials_exception
    except Exception:
        # Catch any other unexpected errors during payload processing (e.g., malformed payload structure)
        # In a production application, it's advisable to log the exception 'e' for debugging.
        raise credentials_exception
    
    return token_data
```