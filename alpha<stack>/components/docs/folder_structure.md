```
aero-fs/
├── .env.example                      # Example environment variables for local development
├── .gitignore
├── README.md
├── Makefile                          # Command runner for common tasks (build, test, run)
├── docker-compose.yml                # Orchestrates local services (api, worker, postgres, redis)
├──
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Continuous Integration pipeline for tests, linting, and builds
│       └── deploy.yml                # Continuous Deployment pipeline to staging/production
│
├── backend/                          # Python Backend (FastAPI API and Celery Workers)
│   ├── Dockerfile.api                # Dockerfile for the API server
│   ├── Dockerfile.worker             # Dockerfile for the Celery workers
│   ├── pyproject.toml                # Project metadata and dependencies (e.g., for Poetry)
│   ├── poetry.lock                   # Lockfile for reproducible Python dependencies
│   ├── aerofs_backend/               # Main source code package
│   │   ├── __init__.py
│   │   ├── api/                      # REST and WebSocket API layer
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # FastAPI dependency injection functions
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── endpoints/        # API route handlers (controllers)
│   │   │       │   ├── __init__.py
│   │   │       │   ├── auth.py       # Authentication endpoints (login, refresh)
│   │   │       │   ├── jobs.py       # Job submission and management endpoints
│   │   │       │   └── users.py      # User management endpoints
│   │   │       └── websockets.py     # WebSocket logic for real-time updates
│   │   ├── auth/                     # Authentication and Authorization logic
│   │   │   ├── __init__.py
│   │   │   ├── jwt.py                # JWT creation and decoding logic
│   │   │   └── security.py           # Password hashing and security utilities
│   │   ├── core/                     # Core application logic and configuration
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py         # Celery application instance setup
│   │   │   └── config.py             # Pydantic settings management (loads from .env)
│   │   ├── db/                       # Database layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Base model and session creation (e.g., SQLAlchemy)
│   │   │   ├── crud/                 # Create, Read, Update, Delete operations
│   │   │   │   ├── __init__.py
│   │   │   │   └── crud_job.py
│   │   │   ├── migrations/           # Database migration scripts (e.g., Alembic)
│   │   │   └── models/               # Database ORM models (e.g., Job, User)
│   │   │       ├── __init__.py
│   │   │       ├── job.py
│   │   │       └── user.py
│   │   ├── integrations/             # Clients for third-party services
│   │   │   ├── __init__.py
│   │   │   └── s3_client.py          # AWS S3 integration logic
│   │   ├── schemas/                  # Pydantic schemas for data validation and serialization
│   │   │   ├── __init__.py
│   │   │   ├── job.py                # Schemas for job creation, status, etc.
│   │   │   ├── token.py              # Schemas for JWT tokens
│   │   │   └── user.py               # Schemas for user creation, etc.
│   │   ├── utils/                    # Shared utility functions
│   │   │   ├── __init__.py
│   │   │   └── logging_config.py     # Centralized logging configuration
│   │   ├── workers/                  # Celery background task definitions
│   │   │   ├── __init__.py
│   │   │   └── processing_tasks.py   # e.g., task_process_file_batch()
│   │   ├── cli.py                    # Typer-based Command Line Interface
│   │   └── main.py                   # FastAPI application entrypoint
│   └── tests/                        # Python tests
│       ├── __init__.py
│       ├── conftest.py               # Pytest fixtures and test setup
│       ├── integration/              # Tests involving multiple components (e.g., API -> DB)
│       │   ├── __init__.py
│       │   └── test_job_flow.py
│       └── unit/                     # Tests for individual functions and classes
│           ├── __init__.py
│           └── test_api_endpoints.py
│
├── rust-core/                        # High-performance Rust processing engine
│   ├── Cargo.toml                    # Rust project manifest and dependencies (crates)
│   ├── build.rs                      # Build script (if needed)
│   └── src/                          # Rust source code
│       ├── error.rs                  # Custom error types for the library
│       ├── lib.rs                    # Library entrypoint with PyO3 Python bindings
│       ├── processing/               # Core data processing modules
│       │   ├── __init__.py
│       │   ├── csv_processor.rs      # Logic for processing CSV files
│       │   ├── parquet_writer.rs     # Logic for writing Parquet files
│       │   └── text_analyzer.rs      # Logic for analyzing text files
│       └── utils.rs                  # Shared Rust utility functions
│
├── frontend/                         # React Frontend Application
│   ├── .eslintrc.cjs                 # ESLint configuration
│   ├── index.html                    # Main HTML entrypoint for Vite
│   ├── package.json
│   ├── playwright.config.ts          # Configuration for Playwright E2E tests
│   ├── tsconfig.json                 # TypeScript configuration
│   ├── vite.config.ts                # Vite build tool configuration
│   ├── public/                       # Static assets that are not processed
│   │   └── favicon.ico
│   ├── src/
│   │   ├── App.tsx                   # Main React application component
│   │   ├── main.tsx                  # Application entrypoint
│   │   ├── assets/                   # Static assets handled by Vite (images, fonts)
│   │   │   └── logo.svg
│   │   ├── components/               # Reusable UI components
│   │   │   ├── common/               # General components (Button, Input, etc.)
│   │   │   └── dashboard/            # Components specific to the dashboard
│   │   │       └── JobStatusBadge.tsx
│   │   ├── hooks/                    # Custom React hooks (e.g., useWebSocket)
│   │   │   └── useJobSocket.ts
│   │   ├── pages/                    # Top-level page components
│   │   │   ├── DashboardPage.tsx
│   │   │   └── JobDetailsPage.tsx
│   │   ├── services/                 # API clients and data fetching logic
│   │   │   ├── api.ts                # Axios or Fetch client setup
│   │   │   └── socket.ts             # WebSocket client setup
│   │   ├── state/                    # Global state management (e.g., Zustand, Redux)
│   │   │   └── jobStore.ts
│   │   ├── styles/                   # Global styles, themes, etc.
│   │   │   └── global.css
│   │   └── utils/                    # Frontend-specific helper functions
│   │       └── formatters.ts
│   └── tests/                        # E2E tests
│       └── e2e/
│           └── dashboard.spec.ts
│
├── docs/                             # Project documentation
│   ├── api/                          # API documentation (e.g., OpenAPI spec, Markdown)
│   ├── architecture/                 # Architecture diagrams and decision records (ADRs)
│   └── user_guide/                   # How-to guides for end-users
│
└── infrastructure/                   # Infrastructure as Code (IaC) and deployment manifests
    └── kubernetes/
        ├── base/                     # Base Kustomize manifests
        ├── overlays/                 # Environment-specific overlays (staging, prod)
        │   ├── production/
        │   └── staging/
        └── services/                 # Manifests for API, workers, etc.
            ├── api-deployment.yml
            └── worker-deployment.yml
```