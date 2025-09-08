project-sanchay/
├── .github/
│   └── workflows/
│       ├── ci-cd.yml          # Main CI/CD pipeline for tests, builds, and releases
│       └── lint.yml           # Code formatting and linting checks
├── .dockerignore              # Specifies files to exclude from Docker images
├── .gitignore                 # Specifies intentionally untracked files to ignore
├── README.md                  # Project overview, setup, and usage instructions
├── pyproject.toml             # Python project metadata and build config (for Maturin)
│
├── assets/
│   ├── icons/                 # Application icons (e.g., .ico, .icns, .png)
│   │   └── app_icon.png
│   └── styles/
│       └── main.qss           # Qt Style Sheet for custom UI theming
│
├── config/
│   ├── __init__.py
│   ├── default.py             # Base configuration settings
│   ├── development.py         # Development-specific overrides
│   ├── production.py          # Production-specific overrides
│   ├── settings.py            # Main entry point for loading configuration
│   └── .env.example           # Template for environment variables
│
├── crates/
│   └── sanchay_core/          # High-performance Rust core engine (as a crate)
│       ├── Cargo.toml         # Rust crate dependencies and metadata (Rayon, Serde)
│       └── src/
│           ├── __tests__/      # Folder for integration-style tests
│           ├── bindings.rs      # PyO3 module definition and Python-facing functions
│           ├── database.rs      # Rust logic for interacting with SQLite/Postgres
│           ├── error.rs         # Custom error types for the Rust core
│           ├── file_processor.rs # Core logic for processing individual files (hashing)
│           ├── lib.rs           # Main Rust library entry point, exports modules
│           └── walker.rs        # Directory traversal logic using Walkdir and Rayon
│
├── docs/
│   ├── ADR/                   # Architecture Decision Records
│   │   └── 001-python-rust-hybrid-approach.md
│   ├── api/                   # Auto-generated API documentation (Sphinx/rustdoc)
│   └── user_guide/
│       └── getting_started.md # Instructions for end-users
│
├── docker/
│   ├── Dockerfile             # Multi-stage Dockerfile for production builds
│   └── docker-compose.yml     # For local development with services like PostgreSQL
│
├── scripts/
│   ├── build.sh               # Helper script to build the application bundle
│   ├── clean.sh               # Script to clean build artifacts
│   └── release.sh             # Script to package and create a release
│
├── src/
│   └── sanchay_app/           # Main Python application source code
│       ├── __init__.py
│       ├── __main__.py          # Main entry point for GUI and CLI
│       ├── api/                 # Optional REST API layer (FastAPI)
│       │   ├── __init__.py
│       │   ├── dependencies.py  # API dependencies
│       │   └── routes.py        # API endpoints (e.g., /jobs)
│       ├── auth/
│       │   ├── __init__.py
│       │   └── credentials.py   # Secure handling of cloud credentials (e.g., AWS S3)
│       ├── cli.py               # Command-Line Interface logic (for headless mode)
│       ├── core/                # Core application logic and orchestration
│       │   ├── __init__.py
│       │   └── job_manager.py   # Manages processing jobs, state, and progress
│       ├── database/
│       │   ├── __init__.py
│       │   ├── connection.py    # Manages SQLite/PostgreSQL connections
│       │   ├── migrations/      # Database schema migrations (e.g., Alembic)
│       │   └── models.py        # Data models (SQLAlchemy ORM)
│       ├── integrations/
│       │   ├── __init__.py
│       │   └── storage_client.py # Client for interacting with AWS S3 or MinIO
│       ├── ui/                  # Frontend components (PySide6)
│       │   ├── __init__.py
│       │   ├── main_window.py   # The main application window shell
│       │   ├── models/          # Qt ItemModels for displaying data
│       │   ├── threads.py       # QThread workers to keep UI responsive
│       │   └── widgets/         # Reusable custom UI widgets
│       │       ├── __init__.py
│       │       └── progress_bar.py
│       └── utils/
│           ├── __init__.py
│           └── logging_config.py # Centralized logging setup
│
└── tests/
    ├── __init__.py
    ├── conftest.py              # Pytest fixtures and test setup
    ├── e2e/                     # End-to-end tests simulating user interaction
    │   └── test_full_scan.py
    ├── integration/
    │   ├── __init__.py
    │   └── test_rust_bridge.py  # Tests the Python-to-Rust function calls
    └── unit/
        ├── __init__.py
        ├── test_job_manager.py  # Unit tests for Python application logic
        └── test_ui_widgets.py   # Unit tests for UI components