from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field


# Base schema for common user properties
# Used for input validation where email is always present
class UserBase(BaseModel):
    email: EmailStr


# Schema for user creation (input from API requests)
# Inherits UserBase and adds the required password field
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Minimum 8 characters")


# Schema for user update (input from API requests, typically for PATCH operations)
# All fields are optional to allow partial updates
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, description="Minimum 8 characters")
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


# Schema for user properties as stored in the database, excluding sensitive fields like hashed password
# This is often used as a base for responses, mapping directly from ORM models
class UserInDBBase(UserBase):
    id: UUID
    is_active: bool = True
    is_superuser: bool = False

    # This configuration is necessary for Pydantic to read data from SQLAlchemy ORM models
    # It tells Pydantic to read attributes from the ORM object (e.g., `user_obj.id`) rather than
    # expecting them as dictionary keys (`user_dict["id"]`).
    model_config = ConfigDict(from_attributes=True)


# Schema for the user data returned in API responses
# It extends UserInDBBase and can be used to add more fields for public consumption if needed
class User(UserInDBBase):
    pass


# Schema for internal use, specifically for representing user data that includes the hashed password
# This schema should not be exposed directly via the API
class UserInDB(UserInDBBase):
    hashed_password: str