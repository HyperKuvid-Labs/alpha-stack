from pydantic import BaseModel, Field, EmailStr
from typing import Optional

# Base Pydantic model for common user attributes
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for the user.")
    email: Optional[EmailStr] = Field(None, description="Optional email address for the user.")

# Pydantic model for user registration (includes the raw password)
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User's password. Must be at least 8 characters long.")

# Pydantic model for user login (username and password)
class UserLogin(BaseModel):
    username: str = Field(..., description="Username for login.")
    password: str = Field(..., description="Password for login.")

# Pydantic model representing user data as stored in the database
# This model includes sensitive fields like 'hashed_password' and ORM-specific fields.
class UserInDB(UserBase):
    id: Optional[int] = Field(None, description="Unique ID of the user (assigned by the database).")
    hashed_password: str = Field(..., description="Hashed password for the user.")
    is_active: bool = Field(True, description="Indicates if the user account is active.")

    class Config:
        from_attributes = True  # Enable ORM mode for Pydantic v2 (allows direct mapping from ORM objects)

# Pydantic model for user data returned in API responses
# This model excludes sensitive fields like 'hashed_password'.
class UserResponse(UserBase):
    id: int = Field(..., description="Unique ID of the user.")
    is_active: bool = Field(..., description="Indicates if the user account is active.")

    class Config:
        from_attributes = True  # Enable ORM mode for Pydantic v2

# Pydantic model for the JWT token returned after successful authentication
class Token(BaseModel):
    access_token: str = Field(..., description="The JWT access token.")
    token_type: str = Field("bearer", description="Type of the token (e.g., 'bearer').")

# Pydantic model for the data contained within the JWT token payload
class TokenData(BaseModel):
    username: Optional[str] = Field(None, description="The subject ('sub') of the token, typically the username.")
