import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.models.base import Base


class JobStatus(enum.Enum):
    """
    Enum for the possible statuses of a processing job.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """
    SQLAlchemy ORM model for the 'jobs' table.

    Represents a single data processing job within the Pravah system.
    Stores information about the job's status, parameters, results,
    and timestamps.
    """
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)

    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    job_type = Column(String(50), nullable=False)  # e.g., 'file_scan', 'image_resize', 'csv_extract'

    input_path = Column(String, nullable=False)  # Path or URI (e.g., s3://bucket/key) to source data
    output_path = Column(String, nullable=True)  # Path or URI to destination for processed data

    parameters = Column(JSONB, nullable=True)  # JSON for job-specific configuration (e.g., resize dimensions)
    results = Column(JSONB, nullable=True)  # JSON for storing summary results (e.g., {'files_processed': 100})

    error_message = Column(Text, nullable=True)  # Detailed error message if the job failed

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Defines a relationship to the User model, assuming 'User' model
    # is defined in app.db.models.user.py and has __tablename__ = "users".
    user = relationship("User", back_populates="jobs")

    def __repr__(self):
        return (
            f"<Job(id='{self.id}', status='{self.status.value}', "
            f"job_type='{self.job_type}', input_path='{self.input_path}')>"
        )