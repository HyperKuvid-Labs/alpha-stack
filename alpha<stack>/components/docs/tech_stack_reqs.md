# Technical Stack Documentation

### Project Title
AeroFS: High-Performance File & Data Processor

### Core Technologies

#### Programming Languages
*   **Python (v3.10+)**: The primary language for the application's backend API, business logic, and orchestration.
    *   **Justification**: Python offers a vast ecosystem of libraries, rapid development capabilities, and is the lingua franca for data science and scripting. It will act as the "glue" that connects the user interface to the high-performance core.
*   **Rust (stable toolchain)**: Used for building the core processing engine that handles CPU-intensive and memory-sensitive tasks.
    *   **Justification**: Rust provides C-level performance with memory safety guarantees, preventing common bugs like null pointer dereferencing and buffer overflows. Its concurrency features are ideal for parallelizing file I/O and data manipulation, which is critical for processing large datasets efficiently.

#### Frameworks & Libraries
*   **Python Backend**:
    *   `FastAPI (v0.95+)`: A modern, high-performance web framework for building the REST API.
        *   **Reason**: Its asynchronous nature (built on Starlette and Pydantic) integrates well with I/O-bound tasks and provides automatic data validation and API documentation (Swagger UI/ReDoc).
    *   `PyO3 (v0.18+)`: The bridge for creating Python bindings for the Rust core library.
        *   **Reason**: It provides seamless and efficient interoperability between Python and Rust, allowing us to call compiled Rust functions directly from Python with minimal overhead.
    *   `Celery (v5.2+)`: A distributed task queue for managing background processing jobs.
        *   **Reason**: It enables asynchronous execution of long-running file processing tasks, preventing API timeouts and allowing for horizontal scaling of processing workers.
    *   `Typer (v0.9+)`: For building a powerful Command Line Interface (CLI).
        *   **Reason**: Provides a simple way to create a CLI for power users and automation scripts, exposing the core processing features directly.
*   **Rust Core**:
    *   `rayon (v1.7+)`: A data-parallelism library for Rust.
        *   **Reason**: Simplifies the process of converting sequential computations (e.g., iterating over lines in a file or entries in a directory) into parallel ones, fully leveraging multi-core processors.
    *   `tokio (v1.28+)`: An asynchronous runtime for writing network applications and handling I/O.
        *   **Reason**: Essential for building a non-blocking, concurrent file processing engine that can handle thousands of simultaneous I/O operations.
    *   `serde (v1.0+)`: A framework for serializing and deserializing Rust data structures efficiently.
        *   **Reason**: Crucial for exchanging structured data (like JSON or other formats) between the Rust core, the Python backend, and external systems.
*   **Frontend**:
    *   `React (v18+)` with `Vite`: A JavaScript library for building user interfaces.
        *   **Reason**: Its component-based architecture is ideal for creating a modular and maintainable UI. The vast ecosystem and community support ensure access to high-quality libraries for charting, data grids, and state management.

#### Databases & Storage
*   **Primary Database**: `PostgreSQL (v15+)`
    *   **Rationale**: A robust and reliable open-source object-relational database. It will store structured metadata about files, processing job definitions, job history, user accounts, and application state. Its support for JSONB is excellent for storing flexible metadata, and its transactional integrity is crucial for job management.
*   **Cache & Message Broker**: `Redis (v7+)`
    *   **Rationale**: An in-memory data store used for two purposes:
        1.  **Job Queue Broker**: To manage the queue of processing tasks for Celery workers, decoupling the API from the background processors.
        2.  **Caching & Real-time Updates**: To cache frequently accessed data and to push real-time progress updates (e.g., percentage complete) to the frontend via WebSockets.

#### Infrastructure & Deployment
*   **Cloud Provider**: `Amazon Web Services (AWS)`
    *   **Rationale**: Offers a mature and comprehensive suite of services that align perfectly with the project's needs for scalability and managed infrastructure (e.g., S3 for object storage, RDS for PostgreSQL, ElastiCache for Redis).
*   **Containerization**: `Docker` & `Docker Compose`
    *   **Rationale**: Standardizes the development and production environments, ensuring consistency. Docker Compose will be used for orchestrating multi-container setups locally (API, workers, DB, Redis).
*   **Orchestration**: `Kubernetes` (via Amazon EKS)
    *   **Rationale**: For production deployment, Kubernetes provides automated scaling, self-healing, and robust management of containerized applications, allowing us to scale the API and worker pools independently based on load.
*   **CI/CD**: `GitHub Actions`
    *   **Rationale**: Tightly integrated with GitHub, providing a streamlined workflow for building, testing, and deploying both the Python and Rust components. A multi-stage Docker build can be used to compile the Rust library and then inject it into the final Python application image.

---

### Architecture Overview

#### System Design Pattern
**Modular Monolith with a Background Worker Queue**. This architecture keeps the core application logic in a single deployable unit for simplicity but decouples the time-consuming tasks into separate, scalable worker processes. This provides a balance between development simplicity and performance scalability.

#### Components & Data Flow
1.  **Frontend (React UI)**: The user interacts with the web interface to define a processing job (e.g., specifying a source directory and the desired operation). The request is sent to the API Server.
2.  **API Server (FastAPI)**:
    *   Receives the request and authenticates the user (e.g., via JWT).
    *   Validates the input parameters.
    *   Creates a job record in the **PostgreSQL** database with a `PENDING` status.
    *   Enqueues the job details (job ID, file paths, parameters) into the **Redis** message queue.
    *   Immediately returns a `202 Accepted` response to the user with the job ID.
3.  **Processing Workers (Python/Celery/Rust)**:
    *   A pool of worker processes listens to the Redis queue.
    *   A worker picks up a job, updates its status to `IN_PROGRESS` in PostgreSQL.
    *   The Python worker script orchestrates the task, calling the highly optimized **Rust Core Library** via PyO3 to perform the heavy lifting (e.g., file parsing, data transformation).
    *   The Rust core uses `rayon` for multi-core parallelism and `tokio` for async I/O to maximize throughput.
    *   Throughout the process, the worker pushes progress updates (e.g., `{'progress': 55, 'status': 'processing file X'}`) to a Redis Pub/Sub channel.
    *   Upon completion, the worker updates the job status in PostgreSQL to `COMPLETED` or `FAILED` and stores any resulting metadata.
4.  **Real-time Feedback Loop**:
    *   The API Server exposes a WebSocket endpoint.
    *   The Frontend connects to this WebSocket and subscribes to updates for its job ID.
    *   An intermediary service (or the API server itself) listens to the Redis Pub/Sub channel and forwards progress messages from the workers to the appropriate client over the WebSocket.




#### Integration & APIs
*   **Primary API**: A **RESTful API** built with FastAPI will serve the frontend. It will handle user authentication, job submission, and retrieval of job history and results.
*   **Real-time API**: **WebSockets** will be used to provide real-time feedback on job progress to the user interface, creating a more interactive and user-friendly experience.
*   **Internal Communication**: The API server and processing workers communicate asynchronously via a **Redis** message queue, which is a robust and scalable pattern for background task processing.

---

## Requirements Documentation

### Functional Requirements
*   **File/Folder Ingestion**: Users can specify local file paths, directories, or S3 bucket locations for processing.
*   **Configurable Processing Jobs**: Users can select and configure different processing pipelines (e.g., "Extract EXIF data from images", "Convert CSV to Parquet", "Count word frequencies in text files").
*   **Job Management Dashboard**: A UI to view the status of all current and past jobs, including progress, start/end times, and logs.
*   **Results & Output**: Processed data or metadata can be viewed in the UI, downloaded as a file, or saved to a specified destination (e.g., another S3 bucket).

#### Sample User Stories
*   **As a data scientist, I want to** point the application to a folder containing 1,000 large CSV files **so that** I can batch-convert them into the more efficient Parquet format for analysis in a Spark cluster.
*   **As a marketing analyst, I want to** upload a single 5GB log file **so that** the system can parse it, extract user session data, and provide me with an aggregated summary report.
*   **As an administrator, I want to** view a real-time dashboard of all active and queued jobs **so that** I can monitor system load and identify any bottlenecks or failed tasks.

### Non-Functional Requirements
*   **Performance**:
    *   The Rust core must be able to saturate I/O bandwidth on modern SSDs (e.g., > 1 GB/s read performance).
    *   API response times for non-processing requests (e.g., fetching job status) must be < 200ms.
    *   Job submission latency (API call to task being queued) must be < 50ms.
*   **Scalability**:
    *   The system must be able to scale horizontally by adding more processing worker containers.
    *   The architecture should support processing datasets in the terabyte range by scaling out compute resources on Kubernetes.
*   **Reliability**:
    *   Jobs must be durable. If a worker fails, the job should be automatically requeued and retried by another available worker.
    *   The system should have an uptime of 99.9%.
*   **Security**:
    *   All API endpoints must be secured and require authentication (JWT).
    *   Role-Based Access Control (RBAC) to distinguish between regular users and administrators.
    *   All secrets (database credentials, API keys) must be managed via a secrets manager (e.g., AWS Secrets Manager) and not be hardcoded.
    *   Data must be encrypted in transit (TLS 1.2+) and at rest (using AWS S3/EBS encryption).
*   **Monitoring**:
    *   Application metrics (e.g., job throughput, error rates, queue length) will be exposed in Prometheus format.
    *   Dashboards will be created in Grafana to visualize system health.
    *   Centralized logging (e.g., ELK Stack or AWS CloudWatch Logs) for debugging and auditing.
    *   Alerting (via PagerDuty or Slack) for critical failures (e.g., high job failure rate, dead workers).

### Technical Constraints
*   **Core Technology Mandate**: The solution *must* use a combination of Python and Rust as specified in the initial request.
*   **Initial Scope**: The initial release (MVP) will focus on local filesystem and AWS S3 as data sources. Support for other cloud providers can be added later.
*   **Resource Focus**: Development effort should prioritize the performance and correctness of the Rust processing core and the robustness of the job queuing system.

---

## Implementation Recommendations

### Development Approach
*   **Methodology**: **Scrum**. The project will be broken down into 2-week sprints. This agile approach allows for iterative development, regular feedback loops (especially for the UI), and the flexibility to adapt to new requirements.
*   **Testing Practices**:
    *   **Rust Unit Tests**: `cargo test` will be used extensively for testing individual functions and modules within the Rust core.
    *   **Python Unit & Integration Tests**: `pytest` will be used to test the FastAPI endpoints and the Python wrapper around the Rust library. Integration tests will ensure the Python-to-Rust boundary (PyO3) works as expected.
    *   **End-to-End (E2E) Tests**: `Cypress` or `Playwright` will be used to automate user flows from the frontend, ensuring the entire system works together.
    *   **CI Gating**: All tests will be run automatically in the CI pipeline for every pull request. Merging will be blocked if any tests fail.

### CI/CD Design
*   **Tool**: `GitHub Actions`
*   **Workflow**:
    1.  **On Pull Request**:
        *   Trigger two parallel jobs: one for frontend, one for backend.
        *   **Frontend Job**: Install Node.js, run `npm install`, `npm run lint`, and `npm test`.
        *   **Backend Job**:
            *   Install Python and Rust.
            *   Lint and format check both Python (`black`, `ruff`) and Rust (`clippy`, `rustfmt`) code.
            *   Run Rust unit tests (`cargo test`).
            *   Build the Rust library as a Python wheel.
            *   Run Python unit and integration tests (`pytest`).
    2.  **On Merge to `main`**:
        *   All the above tests are run again.
        *   If successful, a multi-stage `Dockerfile` builds the final application image.
            *   Stage 1: Compile the Rust core into a `.so` file.
            *   Stage 2: Copy the `.so` file into a lean Python base image and install Python dependencies.
        *   Push the tagged Docker image to a container registry (e.g., Amazon ECR).
        *   Trigger a deployment to the staging environment (e.g., update the Kubernetes deployment manifest).

### Risk Assessment
*   **Risk 1: Performance Overhead at Python-Rust Boundary**
    *   **Description**: Frequent, small calls between Python and Rust can introduce significant overhead from data serialization/deserialization, negating the performance gains from Rust.
    *   **Mitigation**: Design a "coarse-grained" API for the Rust library. Instead of calling Rust to process a single line, Python should pass a large chunk of data (e.g., a full file path or a large byte buffer) and let Rust handle the internal iteration and parallelism.
*   **Risk 2: Build & Dependency Complexity**
    *   **Description**: Managing two different language ecosystems, build tools (`cargo`, `pip`), and linking them correctly can be complex and brittle.
    *   **Mitigation**:
        *   Use a `Makefile` or `justfile` to create simple, high-level commands for common tasks (`make build`, `make test`).
        *   Employ a mature build tool like `maturin` to simplify building and publishing the Rust-based Python package.
        *   Thoroughly document the build process and maintain a version-locked dependency file (`poetry.lock` or `pip-tools`).
*   **Risk 3: Asynchronous Code Complexity**
    *   **Description**: Managing async code in FastAPI, Celery, and Tokio can be challenging, especially around error handling and resource management.
    *   **Mitigation**:
        *   Maintain clear boundaries. Use Python's `asyncio` for I/O in the web layer and Tokio's runtime within the Rust library. Avoid mixing them directly.
        *   Use structured logging with correlation IDs to trace a single request across all components (API -> Redis -> Worker).
        *   Implement robust error handling and retry logic in Celery workers.

---

## Getting Started

### Prerequisites
*   **Local Machine**:
    *   Python 3.10+ and `pip`
    *   Rust toolchain (via `rustup`)
    *   Docker and Docker Compose
    *   Node.js 18+ and `npm`
    *   `make` (optional, for simplified build commands)
*   **Developer Skillsets**:
    *   Proficiency in Python and web frameworks (FastAPI is a plus).
    *   Intermediate knowledge of Rust, including its ownership model and concurrency primitives.
    *   Familiarity with Docker and basic shell scripting.

### Project Structure
A monorepo structure is recommended to keep all related code in one place.

```
aero-fs/
├── .github/workflows/              # CI/CD pipelines (e.g., ci.yml, deploy.yml)
├── backend/                        # Python application (FastAPI, Celery workers)
│   ├── app/                        # Main application package
│   │   ├── __init__.py
│   │   ├── api/                    # REST API endpoints
│   │   ├── core/                   # Config, settings, core logic
│   │   ├── schemas/                # Pydantic data models
│   │   └── workers/                # Celery task definitions
│   ├── tests/                      # Python tests
│   └── pyproject.toml              # Project metadata and dependencies (using Poetry or PDM)
├── rust-core/                      # The high-performance Rust core library
│   ├── src/                        # Rust source code
│   │   ├── lib.rs                  # Main library file with PyO3 bindings
│   │   └── processing_logic.rs     # Module for file processing
│   └── Cargo.toml                  # Rust dependencies (crates)
├── frontend/                       # React frontend application
│   ├── src/
│   └── package.json
├── .env.example                    # Example environment variables
├── .gitignore
├── docker-compose.yml              # For local development environment
└── Makefile                        # Helper scripts for build, test, run
```

### Configuration
*   **Environment Variables**: Application configuration will be managed via environment variables. A `.env` file will be used for local development and loaded by Pydantic's settings management.
    *   Example `.env.example`:
        ```ini
        # Application Settings
        ENVIRONMENT=development
        API_SECRET_KEY=...

        # Database
        POSTGRES_USER=aero
        POSTGRES_PASSWORD=...
        POSTGRES_DB=aerofs
        POSTGRES_HOST=db

        # Redis
        REDIS_HOST=redis
        ```
*   **Secrets Management**: In production, do not use `.env` files. Instead, inject secrets into the container environment using a secure service like **AWS Secrets Manager** or **HashiCorp Vault**. Kubernetes has native support for mounting secrets as environment variables or files.