```
fusionflow/
├── .github/
│   └── workflows/
│       └── ci_cd_pipeline.yml     # GitHub Actions for CI/CD (lint, test, build, deploy)
├── .vscode/                       # Recommended editor settings for consistency
│   ├── extensions.json
│   └── settings.json
├── app/                           # Main Python application source code
│   ├── __init__.py
│   ├── api/                       # FastAPI web application module
│   │   ├── __init__.py
│   │   ├── deps.py                # FastAPI dependencies (e.g., get_db, get_current_user)
│   │   ├── main.py                # FastAPI app factory and main router setup
│   │   └── routes/                # API endpoint definitions (controllers)
│   │       ├── __init__.py
│   │       ├── auth.py            # Authentication endpoints (/login, /register, /me)
│   │       ├── jobs.py            # Job submission, status, and results endpoints
│   │       └── users.py           # User management endpoints (admin)
│   ├── auth/                      # Authentication & authorization core logic
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic schemas for auth (tokens, credentials)
│   │   └── security.py            # Password hashing, token generation/validation (JWT)
│   ├── config/                    # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py            # Pydantic settings model, loads from .env variables
│   ├── core/                      # Core business logic and shared components
│   │   ├── __init__.py
│   │   └── constants.py           # Application-wide constants (e.g., job statuses)
│   ├── db/                        # Database layer (PostgreSQL)
│   │   ├── __init__.py
│   │   ├── alembic/               # Alembic configuration and migration scripts
│   │   │   ├── versions/          # Individual migration files
│   │   │   ├── env.py
│   │   │   └── script.py.mako
│   │   ├── alembic.ini
│   │   ├── base.py                # Declarative base for ORM models
│   │   ├── models/                # ORM models (e.g., SQLAlchemy)
│   │   │   ├── __init__.py
│   │   │   ├── job.py
│   │   │   └── user.py
│   │   └── session.py             # Database session management
│   ├── schemas/                   # Shared Pydantic schemas (data transfer objects)
│   │   ├── __init__.py
│   │   ├── job.py                 # Schemas for jobs (Create, Update, View)
│   │   ├── msg.py                 # Generic message/status response schemas
│   │   └── user.py                # Schemas for users (Create, View)
│   ├── services/                  # External service integrations
│   │   ├── __init__.py
│   │   └── storage_client.py      # Client for Object Storage (S3/MinIO)
│   ├── ui/                        # Streamlit frontend application
│   │   ├── __init__.py
│   │   ├── app.py                 # Main Streamlit entrypoint
│   │   ├── components/            # Reusable UI components
│   │   │   ├── __init__.py
│   │   │   └── job_status_badge.py
│   │   └── pages/                 # Different pages for the Streamlit app
│   │       ├── __init__.py
│   │       ├── 1_Submit_Job.py
│   │       └── 2_Job_Dashboard.py
│   ├── workers/                   # Celery worker implementation
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery application instance setup
│   │   └── tasks.py               # Celery task definitions (calls Rust core)
│   └── utils/                     # Shared helper functions and utilities
│       ├── __init__.py
│       └── logging_config.py      # Centralized logging configuration
├── crates/                        # Rust workspace for performance-critical code
│   └── fusionflow-core/           # The core Rust processing library
│       ├── src/                   # Rust source code
│       │   ├── error.rs           # Custom error types for the library
│       │   ├── processors/        # Modules for different processing jobs
│       │   │   ├── __init__.rs
│       │   │   ├── csv_aggregator.rs
│       │   │   └── text_extractor.rs
│       │   ├── lib.rs             # Crate root and PyO3 module definition
│       │   └── utils.rs           # Shared Rust utilities (e.g., parallel file walker)
│       └── Cargo.toml             # Rust package manifest and dependencies
├── deployment/                    # Deployment & DevOps artifacts
│   ├── kubernetes/                # Kubernetes manifests
│   │   ├── base/                  # Base Kustomize configurations
│   │   ├── overlays/              # Environment-specific Kustomize overlays (staging, prod)
│   │   └── helm-chart/            # Optional Helm chart for the application
│   └── observability/             # Monitoring and logging configs
│       ├── grafana/               # Grafana dashboard definitions (JSON)
│       └── prometheus/            # Prometheus configuration and alert rules
│           └── alert.rules.yml
├── docs/                          # Project documentation
│   ├── api.md                     # API documentation (can be auto-generated from OpenAPI)
│   ├── architecture.md            # System architecture diagrams and notes
│   └── development_guide.md       # Guide for setting up and developing
├── scripts/                       # Helper scripts for development and operations
│   ├── run_dev.sh                 # Starts local dev environment using Docker Compose
│   ├── run_tests.sh               # Executes the full test suite
│   └── seed_db.py                 # Script to seed database with initial data
├── tests/                         # Python test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures and global test setup
│   ├── integration/               # Tests for component interactions (e.g., API -> DB)
│   │   ├── __init__.py
│   │   ├── test_api_jobs.py
│   │   └── test_workers.py
│   ├── py_rust_bindings/          # Tests for the critical Python-Rust boundary
│   │   ├── __init__.py
│   │   └── test_core_library.py
│   └── unit/                      # Unit tests for individual components in isolation
│       ├── __init__.py
│       ├── test_auth_security.py
│       └── test_db_models.py
├── .dockerignore                  # Specifies files to exclude from Docker image
├── .env.example                   # Example environment variables for local setup
├── .gitignore                     # Specifies files to be ignored by Git
├── docker-compose.yml             # Orchestrates local dev services (app, postgres, redis, minio)
├── Dockerfile                     # Multi-stage Dockerfile for building the production image
├── pyproject.toml                 # Python project metadata (PEP 621) and Maturin build config
└── README.md                      # Project overview, setup instructions, and quick start guide
```