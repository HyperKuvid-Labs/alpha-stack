from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


class Token(BaseModel):
    """
    Pydantic model for the access token response sent to the client.
    """
    access_token: str = Field(..., description="The JWT access token.")
    token_type: str = Field("bearer", description="The type of the token.")


class TokenData(BaseModel):
    """
    Pydantic model for the payload contained within a JWT.
    This schema defines the claims expected when decoding a token.
    """
    user_id: UUID = Field(..., description="The unique identifier of the user.")
    email: EmailStr | None = Field(None, description="The email address of the user (optional).")
    sub: str = Field(..., description="The subject of the token, typically the user's ID string.")
    roles: list[str] = Field([], description="List of roles assigned to the user for RBAC.")
    exp: datetime | None = Field(None, description="Expiration timestamp of the token (UTC).")