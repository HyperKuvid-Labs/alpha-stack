from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict


class JobStatusEnum(str, Enum):
    """Enum for the status of a processing job."""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobBase(BaseModel):
    """Base model for common job attributes."""
    input_path: str = Field(..., description="The source path for files to be processed (local filesystem path or S3 URI).")
    output_path: str = Field(..., description="The destination path for processed files (local filesystem path or S3 URI).")


class JobCreateRequest(JobBase):
    """Schema for creating a new processing job."""
    processing_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="A dictionary of configuration options for the processing pipeline. "
                    "Example: {'file_type': 'csv', 'extract_headers': True, 'compression': 'gzip', 'image_resize_px': 1024}."
    )
    # Future enhancements might include: user_id: Optional[UUID], callback_url: Optional[str]


class JobResponse(JobBase):
    """Schema for returning detailed job information, including status and results."""
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode for SQLAlchemy models

    id: UUID = Field(..., description="Unique identifier for the job.")
    status: JobStatusEnum = Field(..., description="Current status of the job.")
    created_at: datetime = Field(..., description="Timestamp when the job was created.")
    updated_at: datetime = Field(..., description="Timestamp when the job was last updated.")
    started_at: Optional[datetime] = Field(None, description="Timestamp when the job started processing.")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the job completed (success or failure).")
    error_message: Optional[str] = Field(None, description="Error message if the job failed.")
    summary: Optional[Dict[str, Any]] = Field(
        None,
        description="A summary of the job's results, e.g., {'files_processed': 100, 'total_size_mb': 500, 'extracted_headers': ['col1', 'col2']}."
    )


class HealthCheckResponse(BaseModel):
    """Schema for the health check endpoint."""
    status: str = Field("healthy", description="Status of the application.")
    timestamp: datetime = Field(..., description="Current server time (UTC).")
    version: str = Field(..., description="Application version.")


class UserBase(BaseModel):
    """Base model for common user attributes."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username.")
    email: EmailStr = Field(..., description="Unique email address.")


class UserCreateRequest(UserBase):
    """Schema for creating a new user account."""
    password: str = Field(..., min_length=8, description="User password.")


class UserResponse(UserBase):
    """Schema for returning user details."""
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode for SQLAlchemy models

    id: UUID = Field(..., description="Unique identifier for the user.")
    is_active: bool = Field(True, description="Whether the user account is active.")
    created_at: datetime = Field(..., description="Timestamp when the user account was created.")
    updated_at: datetime = Field(..., description="Timestamp when the user account was last updated.")


class MessageResponse(BaseModel):
    """Generic schema for returning simple messages or acknowledgments."""
    message: str = Field(..., description="A descriptive message or status.")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional additional details related to the message.")