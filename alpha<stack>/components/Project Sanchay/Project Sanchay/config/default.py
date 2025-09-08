import os
from typing import Literal, Optional

# --- Application General Settings ---
APP_NAME: str = "Sanchay"
APP_VERSION: str = "0.1.0" # Initial application version

# --- Logging Settings ---
# NFR: The application must produce structured logs (e.g., JSON format)
# NFR: Key performance metrics should be logged for analysis.
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json") # Options: "json", "plain"
LOG_FILE_PATH: Optional[str] = os.getenv("LOG_FILE_PATH", None) # If None, logs to console/stderr

# --- Database Settings ---
# Primary Database: SQLite for desktop. Scalable Database Option: PostgreSQL.
# DATABASE_TYPE determines which set of connection parameters is used.
DATABASE_TYPE: Literal["sqlite", "postgresql"] = os.getenv("DATABASE_TYPE", "sqlite").lower()

# SQLite-specific settings
SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./sanchay_metadata.db")

# PostgreSQL-specific settings (expected to be overridden by environment variables in production)
# These are deliberately set to None or default values for a non-sensitive base configuration.
POSTGRES_HOST: Optional[str] = os.getenv("POSTGRES_HOST", None)
POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER: Optional[str] = os.getenv("POSTGRES_USER", None)
# POSTGRES_PASSWORD should NEVER have a default value here; it MUST come from environment or secrets.
POSTGRES_PASSWORD: Optional[str] = os.getenv("POSTGRES_PASSWORD", None)
POSTGRES_DB: Optional[str] = os.getenv("POSTGRES_DB", None)

# --- Rust Core Engine Settings ---
# These settings influence the performance and resource utilization of the Rust core.
# MAX_PARALLEL_WALK_THREADS: 0 means Rayon will choose based on CPU cores.
MAX_PARALLEL_WALK_THREADS: int = int(os.getenv("MAX_PARALLEL_WALK_THREADS", 0))
# FILE_READ_BUFFER_SIZE: Buffer size in bytes for reading files (e.g., for hashing).
FILE_READ_BUFFER_SIZE: int = int(os.getenv("FILE_READ_BUFFER_SIZE", 65536)) # Default to 64 KB

# --- User Interface (UI) Settings (PySide6) ---
UI_THEME_FILE: str = os.getenv("UI_THEME_FILE", "assets/styles/main.qss")

# --- Integrations Settings (e.g., Cloud Object Storage) ---
# NFR: The application should be able to process files directly from object storage.
STORAGE_PROVIDER: Literal["local", "s3", "minio"] = os.getenv("STORAGE_PROVIDER", "local").lower()

# AWS S3 specific settings
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME: Optional[str] = os.getenv("S3_BUCKET_NAME", None)
# AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY should come from environment variables or IAM roles.

# MinIO specific settings
MINIO_ENDPOINT: Optional[str] = os.getenv("MINIO_ENDPOINT", None)
# MINIO_ACCESS_KEY and MINIO_SECRET_KEY should come from environment variables or a secrets manager.
MINIO_ACCESS_KEY: Optional[str] = os.getenv("MINIO_ACCESS_KEY", None)
MINIO_SECRET_KEY: Optional[str] = os.getenv("MINIO_SECRET_KEY", None)
MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "true").lower() == "true" # Use HTTPS by default

# --- Job Management Settings ---
JOB_STATUS_REFRESH_INTERVAL_SECONDS: int = int(os.getenv("JOB_STATUS_REFRESH_INTERVAL_SECONDS", 1))

# --- Command-Line Interface (CLI) Settings ---
CLI_DEFAULT_OUTPUT_FORMAT: Literal["json", "table"] = os.getenv("CLI_DEFAULT_OUTPUT_FORMAT", "table").lower()
CLI_ENABLE_PROGRESS_BAR: bool = os.getenv("CLI_ENABLE_PROGRESS_BAR", "true").lower() == "true"