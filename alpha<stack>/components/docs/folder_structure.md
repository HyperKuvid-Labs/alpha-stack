```
high-performance-filer/
├── .env.example                # Example environment variables for local development
├── .gitignore
├── Dockerfile                  # Multi-stage Dockerfile for production builds
├── LICENSE
├── README.md
├── poetry.lock                 # Locked Python dependencies for reproducible builds
├── pyproject.toml              # Central project config for Poetry (Python) and Maturin (Rust)
├── rust-toolchain.toml         # Pins the project's Rust compiler version for consistency
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # GitHub Actions pipeline: lint, test, build, deploy
│
├── docs/
│   ├── api/                    # Contains generated API documentation
│   │   └── openapi.json
│   ├── architecture.md         # In-depth explanation of architectural decisions
│   └── developer_guide.md      # Guide for setting up, developing, and contributing
│
├── rust_core/                  # The high-performance Rust core engine (a Cargo crate)
│   ├── Cargo.toml              # Rust dependencies (pyo3, rayon, tokio, etc.)
│   ├── Cargo.lock              # Locked Rust dependencies
│   └── src/
│       ├── lib.rs              # Main library entry point, PyO3 module definition, FFI boundary
│       ├── processing/
│       │   ├── mod.rs          # Module declaration for processing logic
│       │   ├── batch.rs        # Logic for batch operations (move, copy, rename)
│       │   ├── report.rs       # Logic for generating manifests and reports
│       │   └── scanner.rs      # Core directory scanning logic using walkdir/rayon
│       ├── core/
│       │   ├── mod.rs
│       │   ├── file_info.rs    # Structs and models for file metadata
│       │   ├── filters.rs      # Filtering logic (by size, date, name, regex)
│       │   └── progress.rs     # Progress reporting callback mechanisms to Python
│       ├── db/
│       │   ├── mod.rs
│       │   └── cache.rs        # SQLite interaction logic (using rusqlite) for metadata/caching
│       ├── integrations/
│       │   ├── mod.rs
│       │   └── s3.rs           # Optional: High-performance AWS S3 client logic
│       └── utils/
│           ├── mod.rs
│           ├── error.rs        # Custom Rust error types and conversion to Python exceptions (PyErr)
│           └── path.rs         # Path sanitization and validation utilities to prevent traversal attacks
│
├── src/
│   └── my_app/                 # The Python application source code (a Python package)
│       ├── __init__.py
│       ├── main.py             # Main application entrypoint (instantiates FastAPI and Typer)
│       ├── api/                # FastAPI web API module
│       │   ├── __init__.py
│       │   ├── dependencies.py # Shared API dependencies (e.g., for auth)
│       │   ├── middleware.py   # Custom API middleware (e.g., logging, timing)
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── jobs.py     # Endpoints for managing/querying long-running tasks
│       │       ├── scan.py     # Endpoints for initiating scans and operations
│       │       └── system.py   # Endpoints for /health and /metrics (NFR-5)
│       ├── auth/
│       │   ├── __init__.py
│       │   └── security.py     # API key validation or other security schemes
│       ├── cli/                # Typer CLI commands module
│       │   ├── __init__.py
│       │   └── commands.py     # CLI command definitions (e.g., `my-app scan ...`)
│       ├── core/
│       │   ├── __init__.py
│       │   └── orchestrator.py # Business logic that calls the Rust core and orchestrates tasks
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py     # Pydantic-based settings management (loads from .env)
│       ├── db/
│       │   ├── __init__.py
│       │   ├── crud.py         # CRUD operations for metadata/cache DB
│       │   ├── database.py     # SQLite connection and session management (Python side)
│       │   └── models.py       # Data models for the database (e.g., SQLAlchemy or Pydantic)
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── tasks.py        # Pydantic schemas for API requests and responses
│       └── utils/
│           ├── __init__.py
│           └── logging.py      # Structured logging configuration
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures and global test setup
    ├── benchmarks/             # Performance benchmarks using `hyperfine` or `pytest-benchmark`
    │   └── bench_rust_core.py
    ├── integration/
    │   ├── __init__.py
    │   └── test_end_to_end.py  # Tests calling Python API which calls the compiled Rust library
    └── unit/
        ├── __init__.py
        ├── test_api.py         # Unit tests for FastAPI endpoints (mocking the core orchestrator)
        ├── test_cli.py         # Unit tests for Typer commands
        └── test_orchestrator.py # Unit tests for Python business logic (mocking the Rust FFI call)
```