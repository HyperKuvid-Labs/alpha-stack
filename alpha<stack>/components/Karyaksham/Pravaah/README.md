# Karyaksham - Efficient Data Processing Platform

**Karyaksham** (Sanskrit/Hindi: कार्याक्षम, meaning "Efficient" or "Capable") is a high-performance, scalable, and efficient application designed for demanding data processing tasks. It leverages a hybrid architecture combining the rapid development capabilities of Python with the raw speed and memory safety of Rust, making it ideal for handling large datasets asynchronously.

## Key Features

*   **Secure Multi-User File Management:** Robust authentication and authorization ensure users can only access their own files and jobs.
*   **Large Dataset Uploads:** Supports file uploads up to 50 GB directly to object storage via presigned URLs, offloading the API server.
*   **Configurable Processing Pipeline:** Define custom processing steps (filter, aggregate, transform, format conversion like CSV to Parquet) for your datasets.
*   **Asynchronous Job Execution & Monitoring:** All processing jobs run in the background with real-time status updates (Pending, Running, Succeeded, Failed) and log access.
*   **Results Download:** Easily download processed files once jobs are complete.

## Technical Stack

Karyaksham is built using a modern, performant, and reliable technology stack:

*   **Programming Languages:** Python (3.11+), Rust (Latest Stable)
*   **Python Stack:** FastAPI, PyO3 (Rust bindings), Celery (Distributed Task Queue), Polars (Fast DataFrame)
*   **Rust Stack:** Rayon (Parallelism), Tokio (Async Runtime), Serde (Serialization)
*   **Databases:** PostgreSQL (v15+) for primary data and metadata.
*   **File Storage:** Object Storage (AWS S3, Google Cloud Storage, MinIO) for raw and processed files.
*   **Cache & Message Broker:** Redis (v7+) for Celery and caching.
*   **Containerization:** Docker & Docker Compose
*   **Orchestration:** Kubernetes (K8s) for production deployment.
*   **CI/CD:** GitHub Actions

## Architecture Overview

Karyaksham employs a **Hybrid Monolith with Asynchronous Task Processing** pattern. The core API is a single deployable unit, while heavy computations are offloaded to an asynchronous task queue. This design ensures scalability from day one and provides a clear path for future microservices evolution.

**Core Components & Data Flow:**

1.  **UI (Frontend):** Users interact with the application to upload files, configure jobs, and monitor status.
2.  **Python API (FastAPI):** Handles user authentication, manages jobs, generates presigned URLs for direct file uploads to Object Storage, and dispatches processing tasks to the Celery queue.
3.  **Message Broker (Redis):** Decouples the API from the processing workers by holding the queue of tasks.
4.  **Processing Workers (Celery):** Python processes that pick up tasks from the queue, orchestrate the job, and invoke the Rust Engine for core processing. They update job status in PostgreSQL.
5.  **Rust Engine (PyO3 Module):** A high-performance, compiled Rust library called directly from Python workers. It streams data from Object Storage, performs CPU-bound transformations with parallel processing, and streams results back to Object Storage.
6.  **Database (PostgreSQL):** The central source of truth for all application metadata, user accounts, and job definitions.
7.  **Object Storage (S3/MinIO):** Stores all large raw and processed files, providing scalable and durable storage.

**Example Data Flow (CSV Filtering):**
A user uploads a CSV file via a presigned S3 URL. The FastAPI backend dispatches a task to Celery. A worker picks up the task, invokes the Rust engine. The Rust engine streams the CSV, applies filters, and streams the filtered data to a new S3 location. The worker then updates the job status in PostgreSQL, and the UI provides a download link.

## Performance & Scalability Highlights

*   **API Response Time:** Under 150ms for metadata operations.
*   **Processing Throughput:** Capable of processing a 1 GB standard CSV file (e.g., filtering) in under 45 seconds on standard compute instances.
*   **Horizontal Scalability:** Processing workers autoscale based on queue length, designed to handle over 100 concurrent jobs.
*   **Reliability:** 99.9% API uptime target, with fault-tolerant job processing and automatic retries.
*   **Observability:** Integrated with Prometheus for metrics, structured logging (forwarded to centralized service), and alerting for critical conditions.

## Getting Started (Local Development)

To run Karyaksham locally, you'll need Docker and Docker Compose.

### Prerequisites

*   **Docker**
*   **Docker Compose**
*   **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/karyaksham.git
cd karyaksham
```

### 2. Environment Configuration

Copy the example environment file and update it with your desired local configurations. For local development, the defaults for MinIO, PostgreSQL, and Redis (as defined in `infrastructure/docker-compose.yml`) are usually sufficient.

```bash
cp .env.example .env
# You can open .env and modify variables if needed
```

### 3. Build and Run Services with Docker Compose

This command will build the Docker images (including compiling the Rust engine within the `backend` image), start all necessary services (PostgreSQL, Redis, MinIO, FastAPI API, Celery worker), and run database migrations.

```bash
docker-compose -f infrastructure/docker-compose.yml up --build -d
```

*   The `-f infrastructure/docker-compose.yml` specifies the path to the Docker Compose file.
*   `--build` ensures that images are rebuilt, including the Rust engine.
*   `-d` runs services in detached mode (in the background).

Wait a few moments for all services to initialize. You can check their status with `docker-compose -f infrastructure/docker-compose.yml ps`.

### 4. Run the Frontend (Optional, but Recommended for Full Experience)

The frontend application needs to be run separately.

```bash
cd frontend
npm install # or yarn install
npm run dev # or yarn dev
```

This will typically start the frontend development server on `http://localhost:3000` (or similar).

### Accessing Services

*   **FastAPI API:** Usually available at `http://localhost:8000` (check `docker-compose.yml` for port mapping). The OpenAPI documentation (Swagger UI) will be at `http://localhost:8000/docs`.
*   **MinIO Console:** Check `docker-compose.yml` for MinIO console port (e.g., `http://localhost:9001`). Use `minioadmin`/`minioadmin` for credentials.
*   **PostgreSQL:** Accessible from your host if you've mapped its port, or directly from other containers using the service name `db`.
*   **Redis:** Accessible from your host if you've mapped its port, or directly from other containers using the service name `redis`.

## Testing

Karyaksham utilizes a comprehensive testing strategy:

*   **Unit Tests:** Thorough tests for individual functions and modules in both Python (`pytest`) and Rust (`cargo test`).
*   **Integration Tests:** Verify interactions between components, especially the Python-Rust FFI boundary and the API-to-Celery workflow.
*   **End-to-End (E2E) Tests:** Simulated user journeys from the UI through the entire backend stack using Playwright.
*   All tests are run automatically as part of the CI/CD pipeline, ensuring code quality before merges.

## Deployment

The application is containerized using Docker and orchestrated with Kubernetes for production deployments. A robust CI/CD pipeline (GitHub Actions) automates linting, testing, building multi-stage Docker images, and deploying to staging and production environments.

## Contributing

We welcome contributions! Please refer to our `CONTRIBUTING.md` (to be created) for guidelines on how to set up your development environment, run tests, and submit pull requests.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.