{project-root}/
├── .env.example # Template for local development environment variables
├── .github/
│   └── workflows/
│       ├── ci.yml # Runs linting, tests, and build checks on PRs
│       └── cd.yml # Deploys to staging/production on merge/tag
├── .gitignore # Specifies intentionally untracked files to ignore
├── README.md # Project overview, setup, and usage instructions
├── backend/
│   ├── pyproject.toml # Python project metadata and dependencies (PDM/Poetry)
│   ├── src/
│   │   ├── karyaksham_api/
│   │   │   ├── __init__.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   └── v1/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── api.py # Aggregates all v1 routers
│   │   │   │       └── endpoints/
│   │   │   │           ├── __init__.py
│   │   │   │           ├── auth.py # Authentication endpoints (login, register)
│   │   │   │           ├── jobs.py # Endpoints for managing processing jobs
│   │   │   │           └── users.py # User management endpoints
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── jwt.py # Logic for creating and decoding JWTs
│   │   │   │   └── security.py # Password hashing, RBAC dependencies
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   └── config.py # Pydantic settings management (loads from .env)
│   │   │   ├── crud/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py # Base CRUD class with common methods
│   │   │   │   ├── crud_job.py # Data access logic for the Job model
│   │   │   │   └── crud_user.py # Data access logic for the User model
│   │   │   ├── db/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── migrations/ # Alembic directory for database migrations
│   │   │   │   │   ├── versions/ # Contains individual migration scripts
│   │   │   │   │   ├── env.py # Alembic runtime environment configuration
│   │   │   │   │   └── script.py.mako # Migration script template
│   │   │   │   ├── models/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── job.py # SQLAlchemy model for processing jobs
│   │   │   │   │   └── user.py # SQLAlchemy model for users
│   │   │   │   └── session.py # Database session creation and management
│   │   │   ├── integrations/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── object_storage.py # Client for S3, GCS, or MinIO
│   │   │   │   └── redis_client.py # Wrapper for Redis connections
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── job.py # Pydantic schemas for job creation and response
│   │   │   │   ├── token.py # Pydantic schemas for JWT tokens
│   │   │   │   └── user.py # Pydantic schemas for user data
│   │   │   ├── static/
│   │   │   │   └── favicon.ico # Example static asset for API docs
│   │   │   ├── utils/
│   │   │   │   ├── __init__.py
│   │   │   │   └── helpers.py # Miscellaneous utility functions
│   │   │   └── main.py # FastAPI application entry point
│   │   └── karyaksham_workers/
│   │       ├── __init__.py
│   │       ├── celery_app.py # Celery application instance and configuration
│   │       └── tasks/
│   │           ├── __init__.py
│   │           └── processing.py # Celery tasks that call the Rust engine
├── docs/
│   ├── C4/ # C4 model diagrams for architecture visualization
│   │   ├── level-1-context.puml
│   │   └── level-2-container.puml
│   ├── adrs/ # Architecture Decision Records
│   │   └── 001-hybrid-monolith-with-ffi.md
│   ├── api.md # Details on API usage and authentication
│   └── setup.md # Developer setup and getting started guide
├── frontend/
│   ├── public/
│   │   └── index.html # Main HTML entry point for the SPA
│   ├── src/
│   │   ├── App.tsx # Main application component (React example)
│   │   ├── assets/ # Static assets like images, fonts, and CSS
│   │   ├── components/ # Reusable UI components
│   │   ├── hooks/ # Custom React hooks
│   │   ├── pages/ # Top-level page components
│   │   ├── services/
│   │   │   └── apiClient.ts # Typed client for interacting with the backend API
│   │   └── main.tsx # Application entry point
│   ├── .eslintrc.cjs # ESLint configuration
│   ├── index.html # Development entry point for Vite
│   ├── package.json # NPM dependencies and scripts
│   └── tsconfig.json # TypeScript configuration
├── infrastructure/
│   ├── Dockerfile # Multi-stage Dockerfile for API and workers
│   ├── .dockerignore # Files to exclude from the Docker build context
│   ├── docker-compose.yml # Orchestrates services for local development
│   ├── kubernetes/
│   │   ├── base/ # Common Kustomize resources for all environments
│   │   │   ├── configmap.yaml
│   │   │   ├── deployment-api.yaml
│   │   │   ├── deployment-worker.yaml
│   │   │   ├── kustomization.yaml
│   │   │   └── service.yaml
│   │   └── overlays/
│   │       ├── production/
│   │       │   ├── kustomization.yaml
│   │       │   └── scaling-patch.yaml
│   │       └── staging/
│   │           ├── kustomization.yaml
│   │           └── replica-count-patch.yaml
│   └── scripts/
│       ├── entrypoint.sh # Container entrypoint script
│       └── run_migrations.sh # Script to apply Alembic migrations
├── rust_engine/
│   ├── Cargo.toml # Rust crate manifest and dependencies
│   ├── src/
│   │   ├── core/
│   │   │   ├── mod.rs # Core module declaration
│   │   │   ├── data_processor.rs # High-performance data processing logic
│   │   │   └── file_handler.rs # Logic for streaming from object storage
│   │   ├── utils/
│   │   │   ├── mod.rs # Utils module declaration
│   │   │   └── error.rs # Custom error types and conversions
│   │   └── lib.rs # PyO3 module definition exposing functions to Python
└── tests/
    ├── __init__.py
    ├── e2e/
    │   ├── specs/
    │   │   └── job_submission.spec.ts # E2E test for a full user journey
    │   └── playwright.config.ts # Configuration for Playwright
    ├── python/
    │   ├── __init__.py
    │   ├── conftest.py # Global pytest fixtures and test helpers
    │   ├── integration/
    │   │   ├── __init__.py
    │   │   ├── test_api_endpoints.py # Tests API routes with a test client
    │   │   └── test_worker_integration.py # Tests the full Celery job flow
    │   └── unit/
    │       ├── __init__.py
    │       ├── test_auth.py # Unit tests for security functions
    │       └── test_crud_operations.py # Unit tests for DB operations
    └── rust/
        └── bridge_test.py # Python-side test to validate PyO3 bindings