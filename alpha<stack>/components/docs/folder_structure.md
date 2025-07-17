pravah/
├── .dockerignore  # Specifies files to exclude from the Docker build context.
├── .env.example  # Template for environment variables for local development.
├── .gitignore  # Specifies intentionally untracked files to ignore.
├── .github/
│   └── workflows/
│       ├── ci.yml  # Continuous integration pipeline for tests and builds.
│       └── cd.yml  # Continuous deployment pipeline to staging/production.
├── app/  # Main Python application source code (FastAPI).
│   ├── __init__.py
│   ├── api/  # REST API layer (versioned).
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── dependencies.py  # Common FastAPI dependencies (e.g., get_db).
│   │       ├── endpoints/  # Resource-specific API endpoints.
│   │       │   ├── __init__.py
│   │       │   ├── jobs.py  # Endpoints for /jobs.
│   │       │   ├── health.py  # Health check endpoint.
│   │       │   └── users.py  # Endpoints for /users.
│   │       └── schemas.py  # Pydantic models for API request/response validation.
│   ├── auth/  # Authentication and Authorization module.
│   │   ├── __init__.py
│   │   ├── dependencies.py  # Security dependencies for API routes.
│   │   ├── jwt.py  # JWT token generation and validation logic.
│   │   └── rbac.py  # Role-Based Access Control implementation.
│   ├── core/  # Core business logic and application orchestration.
│   │   ├── __init__.py
│   │   ├── jobs.py  # Job orchestration and status tracking logic.
│   │   └── processor.py  # Python-side interface to the Rust core engine.
│   ├── db/  # Database interaction layer.
│   │   ├── __init__.py
│   │   ├── migrations/  # Alembic database migration scripts.
│   │   │   ├── versions/  # Individual migration files.
│   │   │   ├── alembic.ini  # Alembic configuration file.
│   │   │   ├── env.py  # Alembic runtime environment configuration.
│   │   │   └── script.py.mako  # Migration script template.
│   │   ├── models/  # ORM models (e.g., SQLAlchemy).
│   │   │   ├── __init__.py
│   │   │   ├── base.py  # Base model class.
│   │   │   ├── job.py  # Job model for the 'jobs' table.
│   │   │   └── user.py  # User model for the 'users' table.
│   │   └── session.py  # Database session management and engine setup.
│   ├── services/  # Clients for external services and integrations.
│   │   ├── __init__.py
│   │   └── storage.py  # Abstracted client for S3/MinIO/local filesystem.
│   ├── utils/  # Shared utility functions and helpers.
│   │   ├── __init__.py
│   │   └── logging.py  # Structured logging configuration.
│   ├── cli.py  # Typer-based Command Line Interface entrypoint.
│   └── main.py  # FastAPI application entrypoint and middleware setup.
├── config/  # Application configuration management.
│   ├── __init__.py
│   └── settings.py  # Pydantic settings model for loading from environment.
├── docs/  # Project documentation.
│   ├── api/  # API documentation (e.g., OpenAPI spec).
│   │   └── openapi.json  # Auto-generated or static OpenAPI specification.
│   ├── architecture.md  # System architecture and design decisions.
│   └── user_guide.md  # How-to guides for developers and users.
├── k8s/  # Kubernetes manifests for deployment.
│   ├── base/  # Base Kustomize manifests for all environments.
│   │   ├── deployment.yaml
│   │   ├── kustomization.yaml
│   │   └── service.yaml
│   └── overlays/  # Environment-specific patches.
│       ├── production/
│       │   ├── configmap.yaml
│       │   └── kustomization.yaml
│       └── staging/
│           ├── configmap.yaml
│           └── kustomization.yaml
├── pravah_core/  # High-performance Rust engine (Cargo crate).
│   ├── Cargo.toml  # Rust project manifest and dependencies (PyO3, Tokio).
│   └── src/  # Rust source code.
│       ├── engine.rs  # Core file processing and parallel computation logic.
│       ├── error.rs  # Custom error types for the Rust engine.
│       ├── models.rs  # Data structures for internal use (with Serde).
│       └── lib.rs  # Main Rust library entrypoint with PyO3 bindings.
├── scripts/  # Helper scripts for development and operations.
│   ├── build.sh  # Script to build the Rust wheel and Docker image.
│   ├── run_dev.sh  # Script to start the local development server.
│   └── setup.sh  # Development environment setup script.
├── tests/  # Test suite for the Python application.
│   ├── __init__.py
│   ├── conftest.py  # Pytest fixtures and test setup.
│   ├── e2e/  # End-to-end tests simulating user workflows.
│   │   ├── __init__.py
│   │   └── test_full_workflow.py
│   ├── integration/  # Tests for component interactions (e.g., API <-> DB).
│   │   ├── __init__.py
│   │   ├── test_api_endpoints.py
│   │   └── test_rust_bridge.py  # Test Python-to-Rust interface.
│   └── unit/  # Unit tests for individual components in isolation.
│       ├── __init__.py
│       └── test_jobs_core.py
├── ui/  # Frontend components (choose one or develop both).
│   ├── react/  # Option 1: React/Next.js for a full-featured UI.
│   │   ├── package.json  # Frontend node dependencies.
│   │   ├── next.config.js  # Next.js configuration.
│   │   ├── public/  # Static assets like images and fonts.
│   │   │   └── favicon.ico
│   │   └── src/  # React source code.
│   │       ├── components/
│   │       └── pages/
│   └── streamlit/  # Option 2: Streamlit for a data-centric dashboard.
│       ├── dashboard.py  # Main Streamlit application file.
│       └── requirements.txt  # Python dependencies for the Streamlit app.
├── docker-compose.yml  # Orchestrates local dev environment (app, db, storage).
├── Dockerfile  # Multi-stage Dockerfile for building a production image.
├── Makefile  # Convenient command runner for build, test, lint, etc.
├── pyproject.toml  # Python project metadata, dependencies, and build config.
└── README.md  # Project overview, setup, and usage instructions.