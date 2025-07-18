import datetime
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from karyaksham_api.db.session import Base
from karyaksham_api.db.models.user import User  # Importing User model for relationship


class JobStatus(enum.Enum):
    """
    Enum for the status of a processing job.
    """
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """
    SQLAlchemy ORM model for the 'jobs' table.
    Represents a file processing job initiated by a user.
    """
    __tablename__ = "jobs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    owner_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    # Relationship to the User model, back-populates the 'jobs' attribute on User
    owner = relationship("User", back_populates="jobs") 

    status = Column(
        Enum(JobStatus, name="jobstatus", create_type=True),
        default=JobStatus.PENDING,
        nullable=False,
        index=True
    )
    job_type = Column(String(50), nullable=False) # e.g., 'csv_filter', 'parquet_conversion', 'data_aggregation'

    input_file_path = Column(String, nullable=False) # S3/MinIO path to the original file
    output_file_path = Column(String, nullable=True) # S3/MinIO path to the processed output file, set upon success

    parameters = Column(JSONB, nullable=False, default={}) # JSONB to store flexible processing parameters (e.g., filter conditions, column mappings)

    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.now, onupdate=datetime.datetime.now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True) # Timestamp when the job started running
    completed_at = Column(DateTime(timezone=True), nullable=True) # Timestamp when the job finished (succeeded, failed, or cancelled)

    error_message = Column(Text, nullable=True) # Stores a detailed error message if the job fails

    def __repr__(self):
        return (
            f"<Job(id={self.id}, owner_id={self.owner_id}, status='{self.status.value}', "
            f"job_type='{self.job_type}', input='{self.input_file_path[:50]}...')>"
        )