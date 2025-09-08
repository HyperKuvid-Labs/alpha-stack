import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

# Base class for declarative models
Base = declarative_base()

class Job(Base):
    """
    Represents a processing job initiated by the user.
    """
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False, index=True) # e.g., 'scan', 'duplicate_check', 'checksum_gen'
    root_path = Column(Text, nullable=False) # The directory or cloud path being processed
    status = Column(String(20), nullable=False, default='pending', index=True) # e.g., 'pending', 'running', 'completed', 'failed', 'cancelled'
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    total_files_processed = Column(BigInteger, default=0)
    total_errors = Column(Integer, default=0)
    # Store job-specific configuration as JSON string (e.g., hash algorithm, file type filters)
    # Using Text for cross-database compatibility (SQLite, PostgreSQL). For PostgreSQL, JSONB type could be used for advanced querying.
    config_json = Column(Text, default='{}')

    # Relationships
    file_metadata = relationship("FileMetadata", back_populates="job", cascade="all, delete-orphan")
    errors = relationship("ProcessingError", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<Job(id={self.id}, type='{self.job_type}', status='{self.status}', "
                f"root_path='{self.root_path[:50]}...')>")

class FileMetadata(Base):
    """
    Stores metadata for each file processed.
    """
    __tablename__ = 'file_metadata'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    
    path = Column(Text, nullable=False, index=True) # Full path to the file
    filename = Column(String(255), nullable=False, index=True) # Just the filename
    extension = Column(String(50), nullable=True, index=True) # File extension (e.g., 'txt', 'jpg')
    
    size = Column(BigInteger, nullable=False) # File size in bytes
    creation_time = Column(DateTime, nullable=True) # File creation timestamp
    modification_time = Column(DateTime, nullable=True) # File modification timestamp
    
    checksum = Column(String(128), nullable=True, index=True) # e.g., MD5, SHA256 hash
    checksum_type = Column(String(20), nullable=True) # e.g., 'MD5', 'SHA256'
    
    is_duplicate = Column(Boolean, default=False)
    # If this file is a duplicate, link to the ID of the *original* file it's duplicated of.
    # This assumes a primary/secondary duplicate relationship, where one file is chosen as the "original".
    duplicate_of_file_id = Column(Integer, ForeignKey('file_metadata.id'), nullable=True, index=True)
    
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="file_metadata")
    duplicates = relationship("FileMetadata", remote_side=[id], backref="original_file", cascade="all")

    # Ensure uniqueness of file path within a job to prevent redundant entries
    __table_args__ = (
        UniqueConstraint('job_id', 'path', name='_job_path_uc'),
    )

    def __repr__(self):
        return (f"<FileMetadata(id={self.id}, job_id={self.job_id}, "
                f"path='{self.path[:50]}...', size={self.size}, checksum='{self.checksum[:10] if self.checksum else 'None'}')>")

class ProcessingError(Base):
    """
    Stores details about errors encountered during processing of a specific job or file.
    """
    __tablename__ = 'processing_errors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    
    file_path = Column(Text, nullable=True) # Path of the file that caused the error (can be null for job-level errors)
    error_type = Column(String(100), nullable=False, index=True) # e.g., 'permission_denied', 'file_not_found', 'checksum_error', 'database_error'
    message = Column(Text, nullable=False) # Detailed error message
    stack_trace = Column(Text, nullable=True) # Optional: Full stack trace for debugging
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="errors")

    def __repr__(self):
        return (f"<ProcessingError(id={self.id}, job_id={self.job_id}, "
                f"error_type='{self.error_type}', file='{self.file_path[:50] if self.file_path else 'N/A'}')>")

# Helper function to create all tables (for initial setup or testing)
def create_all_tables(engine):
    """
    Creates all tables defined in this module in the specified database engine.
    This function is primarily for initial setup or testing. For production,
    Alembic migrations (defined in database/migrations) should be used.
    """
    Base.metadata.create_all(engine)

# Note: The actual SQLAlchemy Engine and Session management will be handled
# in the `sanchay_app.database.connection` module. This file solely defines the ORM models.