# VēgaFS: High-Performance File & Data Processing Engine

*Vēga (वेग)* is a Sanskrit word for "speed" or "velocity," reflecting the project's core focus on high-performance file operations. VēgaFS is a powerful and efficient solution designed for managing and processing large volumes of files and data. By combining the rapid development capabilities of Python with the raw performance and safety guarantees of Rust, VēgaFS offers a unique hybrid architecture for demanding file system tasks.

## Why VēgaFS?

Traditional file operations can become bottlenecks when dealing with vast datasets. VēgaFS addresses this by:
*   **Unrivaled Performance:** Leveraging Rust for core processing allows for C/C++-level speeds, memory safety, and fearless concurrency.
*   **Developer Agility:** Python provides a rich ecosystem for building the application layer, REST API, and CLI, enabling rapid iteration and integration.
*   **Scalability:** Designed for horizontal scaling, allowing you to process millions of files across distributed environments.
*   **Safety & Reliability:** Rust's compile-time guarantees eliminate common runtime errors, ensuring a stable and secure processing engine.

## Key Features

*   **Parallel File Processing:** Apply custom operations across thousands or millions of files in parallel, utilizing all available CPU cores.
*   **Comprehensive Directory Analysis:** Efficiently calculate statistics for large directory trees, including total size, file/folder counts, largest/smallest files, and file type distributions.
*   **Bulk File Operations:** Perform high-throughput, atomic operations like renaming, moving, and copying files based on user-defined patterns and rules.
*   **Robust Job Management:** Submit, monitor, and retrieve results for long-running processing jobs via a powerful REST API.

## Architecture at a Glance

VēgaFS employs a **Modular Monolith** architecture:

*   **Python Application Layer:** (FastAPI, Typer) Handles external communication (REST API, CLI), orchestrates workflows, and manages job states in PostgreSQL.
*   **Rust Core Library:** (Rayon, Tokio) The high-performance engine for all computationally intensive file processing, accessed directly from Python via `PyO3` bindings within the same process.
*   **PostgreSQL:** Stores structured metadata about files, processing jobs, and results.
*   **Redis:** Serves as an in-memory cache for frequently accessed file system queries and intermediate results.

This design ensures performance by offloading heavy computation to Rust while maintaining the development speed and ecosystem benefits of Python.

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

*   **Python:** Version 3.10 or higher.
*   **Rust:** Latest stable version (install via `rustup.rs`).
*   **Docker & Docker Compose:** For containerized development and deployment.
*   **Maturin:** Python build tool for Rust extensions (`pip install maturin`).

### Project Setup (Recommended: Docker Compose)

The easiest way to get VēgaFS running locally is using Docker Compose, which sets up the application, PostgreSQL, and Redis with a single command.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/vegafs.git # Replace with actual repo URL
    cd vegafs
    ```
2.  **Environment Variables:** Create a `.env` file in the project root, based on `.env.example`, and fill in necessary configurations (e.g., database credentials).
    ```dotenv
    # .env
    DATABASE_URL="postgresql://user:password@db:5432/vegafs_dev"
    REDIS_URL="redis://redis:6379"
    LOG_LEVEL="INFO"
    ```
3.  **Start Services:**
    ```bash
    docker-compose up --build
    ```
    This command will build the Rust core and Python application inside a Docker image, then start all services. The application will be accessible via `http://localhost:8000`.

### Project Setup (Manual - For Advanced Users/Development)

If you prefer to run the application directly on your machine without Docker Compose for core development:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/vegafs.git # Replace with actual repo URL
    cd vegafs
    ```
2.  **Build Rust Core & Install Python Dependencies:**
    ```bash
    maturin develop --release
    pip install -e .
    ```
    `maturin develop` compiles the Rust core and creates Python bindings. `pip install -e .` installs the Python dependencies listed in `pyproject.toml` and makes the project editable.

3.  **Database & Redis:** Ensure PostgreSQL and Redis are running and accessible (e.g., via local installations or separate Docker containers). Update your `.env` file with correct connection strings.

4.  **Run Migrations:** (If database schema needs to be applied/updated; refer to `app/database/migrations` for specifics)
    ```bash
    # Example command using Alembic (if configured)
    alembic upgrade head
    ```

5.  **Start the FastAPI application:**
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```

## Usage

VēgaFS can be interacted with via its RESTful API or a Command-Line Interface (CLI).

### REST API

Once the application is running (e.g., via Docker Compose), the API will be available at `http://localhost:8000`. You can access the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

**Example: Submit a Directory Summarization Job**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "operation_type": "directory_summary",
       "parameters": {
         "path": "/data/my-project-files",
         "recursive": true
       }
     }'
```
The API will return a `job_id` which you can use to monitor the job's status via `GET /api/v1/jobs/{job_id}`.

### Command-Line Interface (CLI)

A CLI tool is available for common operations.

**Example: Summarize a Directory**
```bash
python -m vegafs summarize /data/my-project-files --recursive
```
*(Note: The exact CLI command structure might vary based on `Typer`/`Click` implementation configured in `app/main.py`.)*

## Running Tests

VēgaFS uses Rust's built-in testing framework for the core and `pytest` for the Python application.

*   **Run Rust tests:**
    ```bash
    cd rust_core
    cargo test
    ```
*   **Run Python tests (including integration tests for PyO3 bridge):**
    ```bash
    pytest tests/
    ```
    (Ensure you have built the Rust core with `maturin develop --release` or `maturin build --release` and installed the Python package with `pip install -e .` for Python tests to find the Rust module).

## Contributing

We welcome contributions! Please see our `CONTRIBUTING.md` (to be created) for guidelines on how to submit issues, features, and pull requests.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.