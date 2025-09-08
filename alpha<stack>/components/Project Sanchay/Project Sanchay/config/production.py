```python
"""
Production configuration settings for Project Sanchay.

These settings override or extend the default settings defined in `default.py`
and are specifically tailored for a production environment.
Sensitive information (like database credentials, cloud keys) should
always be sourced from environment variables or a secure secrets manager,
not hardcoded here.
"""

from os import getenv

# --- General Application Settings ---
DEBUG = False
ENVIRONMENT = "production"

# --- Logging Settings ---
# Set the default log level for production. INFO is common for general operations,
# WARNING or ERROR might be used for critical environments.
LOG_LEVEL = getenv("LOG_LEVEL", "INFO").upper()

# --- Database Settings ---
# In production, the DATABASE_PATH for SQLite or DATABASE_URL for PostgreSQL
# should be strictly sourced from environment variables.
# Example placeholder, relying on environment variables to provide the actual values:
# DATABASE_PATH = getenv("DATABASE_PATH") # e.g., "/var/lib/sanchay/sanchay_metadata.db"
# DATABASE_URL = getenv("DATABASE_URL")   # e.g., "postgresql://user:pass@host:port/dbname"

# --- Cloud Storage Settings (AWS S3 / MinIO) ---
# Cloud storage credentials and bucket names must be environment variables
# or fetched from a secure secrets manager.
# S3_BUCKET_NAME = getenv("S3_BUCKET_NAME")
# S3_REGION = getenv("S3_REGION")
# S3_ENDPOINT_URL = getenv("S3_ENDPOINT_URL") # For MinIO or custom S3 compatible storage

# --- API Settings (if FastAPI is enabled for headless operation) ---
# It is common practice to disable interactive API documentation (Swagger UI/ReDoc)
# in production environments for security reasons.
API_DOCS_URL = None
API_REDOC_URL = None

# --- Other production-specific flags or overrides ---
# Disable any development-only features or tools in production.
ENABLE_DEVELOPMENT_TOOLS = False

# Number of Rust worker threads. Default to 0, which means the Rust core
# (e.g., Rayon) will automatically determine the optimal number based on CPU cores.
# Allow overriding this via an environment variable for specific production tuning.
RUST_CORE_THREADS = int(getenv("RUST_CORE_THREADS", "0"))
```