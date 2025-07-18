# Local Development Setup Guide

This document provides step-by-step instructions for setting up the Karyaksham project on your local machine for development and testing.

## 1. Prerequisites

Ensure you have the following software installed on your system:

*   **Git**: For cloning the repository.
    *   [Download Git](https://git-scm.com/downloads)
*   **Python 3.11+**:
    *   We recommend using `pyenv` or `conda` for managing Python versions.
    *   Verify installation: `python3 --version`
*   **Rust Toolchain (Latest Stable)**:
    *   Install via `rustup`: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
    *   Verify installation: `rustc --version`
*   **Docker & Docker Compose**:
    *   Used for running dependent services (PostgreSQL, Redis, MinIO).
    *   [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
    *   Verify installation: `docker --version`, `docker compose version`
*   **Node.js v18+ & npm/yarn**:
    *   Required for the frontend application.
    *   [Download Node.js](https://nodejs.org/en/download/)
    *   Verify installation: `node -v`, `npm -v` or `yarn -v`
*   **PDM (Python Package Manager)**: Our preferred package manager for Python.
    *   Install: `pip install pdm`
    *   Verify installation: `pdm --version`
    *   *Alternatively, if you prefer Poetry*: `pip install poetry`
*   **Maturin**: Tool for building Rust-Python packages.
    *   Install: `pip install maturin`
    *   Verify installation: `maturin --version`

## 2. Project Setup

### 2.1. Clone the Repository

First, clone the Karyaksham repository to your local machine:

```bash
git clone https://github.com/your-org/karyaksham.git # Replace with your actual repository URL
cd karyaksham
```

### 2.2. Environment Variables

The project uses environment variables for configuration. A template file `.env.example` is provided in the project root.

1.  Copy the example file to `.env` in the root directory:
    ```bash
    cp .env.example .env
    ```
2.  Open `.env` using a text editor and review the default settings. For local development, the defaults usually work well, as they are configured to connect to services run by `docker-compose`.
    *   **Important**: Do not commit your `.env` file to version control. It is already included in `.gitignore`.

### 2.3. Start Dependent Services with Docker Compose

Navigate to the `infrastructure/` directory and start the database, message broker, and object storage services using Docker Compose:

```bash
cd infrastructure/
docker compose up -d postgres redis minio
```
*   This command will download the necessary Docker images and start the containers in the background.
*   You can verify the services are running with `docker compose ps`.
*   Once services are up, navigate back to the project root: `cd ..`

## 3. Backend Setup (Python & Rust)

Navigate to the `backend/` directory for backend development:

```bash
cd backend/
```

### 3.1. Compile the Rust Engine

The Rust processing engine needs to be compiled into a Python-compatible wheel. This step uses `maturin` to build the `rust_engine` crate and install it into your Python environment.

```bash
maturin develop --release
```
*   This command compiles the Rust code in `../rust_engine/` and installs it as a Python module in your current `pdm` or `poetry` environment. The `--release` flag ensures optimized performance.

### 3.2. Install Python Dependencies

Install the Python dependencies using PDM. This will also ensure the compiled Rust engine is linked correctly.

```bash
pdm install
```
*   If you are using Poetry:
    ```bash
    poetry install --with dev,test
    ```

### 3.3. Apply Database Migrations

Once the backend dependencies are installed and the `postgres` service is running via Docker Compose, apply the database migrations to set up your schema:

```bash
pdm run alembic upgrade head
```
*   If you are using Poetry:
    ```bash
    poetry run alembic upgrade head
    ```
*   After completing backend setup, navigate back to the project root: `cd ..`

## 4. Frontend Setup

Navigate to the `frontend/` directory:

```bash
cd frontend/
```

### 4.1. Install Node.js Dependencies

```bash
npm install
# Or if you prefer yarn:
# yarn install
```
*   After completing frontend setup, navigate back to the project root: `cd ..`

## 5. Running the Application

Ensure all Docker Compose services are running (`docker compose ps` from `infrastructure/` directory). You will need multiple terminal windows or tabs to run all components concurrently.

### 5.1. Start the FastAPI Application (API)

Open a new terminal, navigate to the `backend/` directory, and start the FastAPI server:

```bash
cd backend/
pdm run uvicorn karyaksham_api.main:app --host 0.0.0.0 --port 8000 --reload
```
*   If you are using Poetry:
    ```bash
    poetry run uvicorn karyaksham_api.main:app --host 0.0.0.0 --port 8000 --reload
    ```
*   The API will be available at `http://localhost:8000`.
*   Swagger UI (API documentation) will be at `http://localhost:8000/docs`.

### 5.2. Start Celery Workers

Open another new terminal, navigate to the `backend/` directory, and start the Celery worker:

```bash
cd backend/
pdm run celery -A karyaksham_workers.celery_app worker -l info --pool=prefork --concurrency=4
```
*   If you are using Poetry:
    ```bash
    poetry run celery -A karyaksham_workers.celery_app worker -l info --pool=prefork --concurrency=4
    ```
*   This worker will pick up tasks dispatched by the FastAPI application. Adjust `--concurrency` based on your CPU cores.

### 5.3. Start Celery Beat (Optional, for scheduled tasks)

If your application has scheduled tasks, you'll need to run Celery Beat. Open yet another new terminal, navigate to the `backend/` directory:

```bash
cd backend/
pdm run celery -A karyaksham_workers.celery_app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```
*   If you are using Poetry:
    ```bash
    poetry run celery -A karyaksham_workers.celery_app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ```

### 5.4. Start the Frontend Application

Open a final new terminal, navigate to the `frontend/` directory, and start the frontend development server:

```bash
cd frontend/
npm run dev
# Or with yarn:
# yarn dev
```
*   The frontend application will typically be available at `http://localhost:5173` (or another port depending on your Vite/React configuration).

## 6. Testing

### 6.1. Running Python Tests

Navigate to the `backend/` directory:

```bash
cd backend/
pdm run pytest tests/python/unit/         # Run unit tests
pdm run pytest tests/python/integration/  # Run integration tests
pdm run pytest tests/python/              # Run all Python tests
```
*   If you are using Poetry:
    ```bash
    poetry run pytest tests/python/unit/
    ```
*   After running tests, navigate back to the project root: `cd ..`

### 6.2. Running Rust Tests

Navigate to the `rust_engine/` directory:

```bash
cd rust_engine/
cargo test
```
*   After running tests, navigate back to the project root: `cd ..`

### 6.3. Running End-to-End (E2E) Tests

Ensure the backend and frontend development servers are running before executing E2E tests. From the project root directory (`karyaksham/`):

```bash
npm run test:e2e
# Or with yarn:
# yarn test:e2e
```

## 7. Troubleshooting

*   **Docker containers not starting**:
    *   Ensure Docker Desktop is running.
    *   Review logs with `docker compose logs` (from `infrastructure/` directory).
*   **Port conflicts**: If a service fails to start, another application might be using the port (e.g., 8000 for API, 6379 for Redis). You can adjust ports in `infrastructure/docker-compose.yml` and your `.env` file if necessary.
*   **"command not found: pdm/poetry/maturin"**: Ensure these tools are installed and your system's PATH environment variable is correctly configured to find their executables.
*   **Rust compilation issues**:
    *   Ensure your Rust toolchain is up-to-date (`rustup update`).
    *   You might need to install necessary C/C++ build tools (e.g., `build-essential` on Debian/Ubuntu, Xcode Command Line Tools on macOS, MSVC build tools on Windows).
*   **Database connection errors**:
    *   Verify the `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` variables in your `.env` file match the `docker-compose.yml` service names and credentials.
    *   Ensure the `postgres` container is healthy (`docker compose ps` from `infrastructure/`).