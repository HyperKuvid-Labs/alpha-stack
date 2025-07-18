```python
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """
    Represents the possible states of a processing job within the system.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobCreate(BaseModel):
    """
    Schema for creating a new processing job.
    This is used for incoming requests to the API when a user wants to start a job.
    """
    input_file_key: str = Field(
        ...,
        description="The unique key/path of the input file in object storage (e.g., S3 object key). "
                    "This key is obtained after a successful presigned URL upload."
    )
    job_type: str = Field(
        ...,
        description="The type of processing job to be executed (e.g., 'csv_filter', 'csv_to_parquet'). "
                    "This dictates which Rust engine function will be invoked."
    )
    parameters: Dict[str, Any] = Field(
        {},
        description="A JSON object containing job-specific parameters required for processing. "
                    "Example: {'filter_column': 'country', 'filter_value': 'India'} for a CSV filter job."
    )
    # The 'user_id' is typically derived from the authentication token
    # and automatically associated with the job on the backend, not provided by the client here.


class JobBase(BaseModel):
    """
    Base schema for representing common attributes of a processing job.
    Used for shared fields between creation and full job representation.
    """
    input_file_key: str = Field(
        ...,
        description="The unique key/path of the input file in object storage."
    )
    output_file_key: Optional[str] = Field(
        None,
        description="The unique key/path of the processed output file in object storage. "
                    "This is populated upon successful job completion."
    )
    job_type: str = Field(
        ...,
        description="The type of processing job that was executed."
    )
    parameters: Dict[str, Any] = Field(
        {},
        description="The job-specific parameters used for this processing instance."
    )
    status: JobStatus = Field(
        JobStatus.PENDING,
        description="The current status of the processing job (e.g., PENDING, RUNNING, COMPLETED, FAILED)."
    )
    user_id: UUID = Field(
        ...,
        description="The unique identifier (UUID) of the user who initiated this job."
    )
    error_message: Optional[str] = Field(
        None,
        description="A detailed error message if the job failed, otherwise None."
    )


class Job(JobBase):
    """
    Full schema for a processing job, including database-generated fields like ID and timestamps.
    This schema is used for responses when retrieving job details from the API.
    """
    id: UUID = Field(
        ...,
        description="The unique identifier (UUID) of the job, assigned by the database."
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp (UTC) when the job was initially created in the system."
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp (UTC) when the job's status or details were last updated."
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Timestamp (UTC) when the job officially began processing by a worker."
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp (UTC) when the job finished processing (either successfully or with failure)."
    )

    class Config:
        """
        Pydantic configuration for the Job model.
        `from_attributes = True` (Pydantic v2+) allows conversion directly from ORM models.
        """
        from_attributes = True


class PresignedUrlRequest(BaseModel):
    """
    Schema for requesting a presigned URL to upload a file to object storage.
    """
    file_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The original name of the file the user intends to upload. Used to generate a unique key."
    )
    content_type: str = Field(
        ...,
        description="The MIME type of the file being uploaded (e.g., 'text/csv', 'application/json')."
    )


class PresignedUrlResponse(BaseModel):
    """
    Schema for the response containing a presigned upload URL and the associated file key.
    """
    upload_url: str = Field(
        ...,
        description="The secure, time-limited URL to which the file should be uploaded directly by the client."
    )
    file_key: str = Field(
        ...,
        description="The unique key/path where the file will be stored in object storage after a successful upload. "
                    "This key should be used in subsequent JobCreate requests."
    )
```