# Pravah: High-Performance File & Data Processing Engine

*(Pravah, a Sanskrit word for "flow" or "stream," reflects the project's goal of creating a fast and efficient data processing pipeline.)*

## Overview

Pravah is a high-performance, scalable file and data processing engine designed to efficiently handle large volumes of data across various storage backends. It leverages the power of Python for its API and orchestration, and Rust for its core, highly concurrent, and memory-safe processing capabilities, making it ideal for tasks ranging from high-speed directory traversal to complex data transformations.

## Key Features

*   **Blazing-fast directory scanning and file traversal:** Optimized for millions of files using Rust's `walkdir` and asynchronous I/O.
*   **Parallel and asynchronous file processing:** Leverages Rust's `Tokio` and `Rayon` to efficiently utilize all available CPU cores and I/O capacity.
*   **Configurable processing pipelines:** Users can define or select predefined processing tasks (e.g., format conversion, data extraction, compression) via the API or CLI.
*   **Robust Job Management:** All operations are managed as jobs with trackable statuses (pending, running, completed, failed) persisted in PostgreSQL.
*   **Versatile Storage Support:** Capable of reading from and writing to local filesystems, Amazon S3, and MinIO object storage.
*   **Powerful REST API:** Built with FastAPI for programmatic access, offering OpenAPI documentation out-of-the-box.
*   **User-friendly Command Line Interface (CLI):** Powered by Typer for scripting and automation of processing tasks.

## Technical Stack

*   **Programming Languages:** Python (3.11+), Rust (Latest Stable)
*   **Web Framework:** FastAPI (v0.100.0+)
*   **Python-Rust Bridge:** PyO3 (v0.20.0+)
*   **Asynchronous Rust Runtime:** Tokio (v1.28.0+)
*   **Data Parallelism (Rust):** Rayon (v1.7.0+)
*   **Serialization (Rust):** Serde (v1.0.0+)
*   **Database:** PostgreSQL (v15+) for metadata and job queue, SQLite for embedded use cases.
*   **Object Storage:** Amazon S3, MinIO
*   **Containerization:** Docker, Docker Compose
*   **Orchestration:** Kubernetes (AWS EKS recommended for production)
*   **CI/CD:** GitHub Actions

## Architecture

Pravah employs a **Modular Monolith with a Core-Plugin Architecture**. The main application logic and REST API are built with **Python (FastAPI)**, providing a flexible and developer-friendly interface for job orchestration and external communication. The performance-critical components, such as high-speed directory traversal, concurrent I/O, and CPU-bound data processing, are implemented in a **Rust core engine (`pravah_core`)**. This Rust core is seamlessly exposed to Python via **PyO3 bindings**, ensuring minimal overhead and maximum efficiency for intensive tasks.

Jobs, their status, and related metadata are persistently stored in **PostgreSQL**. The system supports reading and writing data to various backends, including local filesystems and S3-compatible object storage.

## Getting Started

Follow these steps to set up and run Pravah locally.

### Prerequisites

*   Python 3.11+
*   Rust Toolchain (install via `rustup.rs`)
*   Docker & Docker Compose
*   `make` (or `just`)
*   `pdm` (Python Development Master, install with `pip install pdm`)

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/pravah.git
cd pravah
```

### 2. Environment Configuration

Create a `.env` file for local development by copying the example. This file is ignored by Git and will store your sensitive configurations.

```bash
cp .env.example .env
```

Open `.env` and fill in necessary details. A typical `.env` for local development with Docker Compose services might look like this:

```ini
# Application Settings
LOG_LEVEL=INFO
APP_HOST=0.0.0.0
APP_PORT=8000

# Database
DATABASE_URL=postgresql://user:password@pravah_db:5432/pravah_db

# S3 Storage (MinIO for local development, adjust for AWS S3 in prod)
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=pravah-local-bucket
S3_ENDPOINT_URL=http://pravah_minio:9000
S3_REGION_NAME=us-east-1
S3_USE_SSL=False
```

### 3. Build the Rust Core Engine

Pravah's performance-critical components are written in Rust. You need to compile this into a Python-loadable module.

```bash
make build-rust
```

This command uses `maturin` (configured in `pyproject.toml` and managed by the `Makefile`) to build the Rust `pravah_core` crate and generate a Python wheel, which `pdm` will then use.

### 4. Install Python Dependencies

Install all Python dependencies, including the local Rust wheel.

```bash
pdm install
```

### 5. Run Local Services (Database & Object Storage)

Start the PostgreSQL database and MinIO object storage services using Docker Compose. These are essential for Pravah's operation.

```bash
docker-compose up -d postgres minio
```

### 6. Run Database Migrations

Apply the necessary database schema migrations to your PostgreSQL instance.

```bash
pdm run alembic upgrade head
```

### 7. Run the Pravah Application

#### a. FastAPI Web Server (API)

Start the Pravah API server.

```bash
pdm run start-api
```

The API will be available at `http://localhost:8000`. You can access the interactive OpenAPI documentation (Swagger UI) at `http://localhost:8000/docs`.

#### b. Command Line Interface (CLI)

Explore Pravah's CLI capabilities:

```bash
pdm run python app/cli.py --help
# Example: Create a new job to process files
# pdm run python app/cli.py jobs create --source-path /data/input --destination-path s3://output --processor "extract_headers"
```

#### c. Running the Full Stack with Docker Compose

For a fully containerized local development environment, including the FastAPI application, PostgreSQL, and MinIO:

```bash
docker-compose up --build
```

This will build the Docker image for the Python application (including the compiled Rust core) and run it along with its dependencies. The FastAPI application will be accessible at `http://localhost:8000`.

## Usage Examples

Refer to `docs/user_guide.md` for detailed usage examples and a comprehensive API reference.

In brief, you can create processing jobs by sending a `POST` request to the `/jobs` endpoint, specifying input file paths or directories, and desired processing configurations. You can then monitor the job's status and retrieve results using `GET` requests to `/jobs/{job_id}`.

## Testing

Pravah includes a comprehensive test suite covering unit, integration, and end-to-end scenarios.

*   **Python Unit & Integration Tests:**
    ```bash
    pdm run pytest tests/unit tests/integration
    ```

*   **Rust Core Tests:**
    ```bash
    cd pravah_core
    cargo test
    cd ..
    ```

*   **End-to-End (E2E) Tests:**
    ```bash
    pdm run pytest tests/e2e
    ```

All tests are automatically executed as part of the CI/CD pipeline defined in `.github/workflows/ci.yml`.

## Contributing

We welcome contributions to Pravah! Please ensure your code adheres to our quality standards and that all tests pass. For development, ensure `ruff` (for Python) and `clippy` (for Rust) linters pass before committing.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.