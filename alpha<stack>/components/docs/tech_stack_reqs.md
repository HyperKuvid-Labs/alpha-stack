# Technical Stack Documentation

### Project Title
**Karyaksham** (Sanskrit/Hindi: कार्याक्षम, meaning "Efficient" or "Capable")

This title reflects the core user requirement for a high-performance, efficient application capable of handling demanding data processing tasks.

### Core Technologies

#### **Programming Languages**
- **Python (3.11+)**
  - **Justification:** Python is chosen for its extensive ecosystem, rapid development capabilities, and robust support for web frameworks and data science libraries. It will serve as the primary language for the application's API layer, business logic orchestration, and background job management. Its readability and vast community support make it ideal for building the user-facing components quickly.
- **Rust (Latest Stable)**
  - **Justification:** Rust is selected for its unparalleled performance, memory safety without a garbage collector, and fearless concurrency. It will be used to build the core file processing engine, which will be compiled into a native Python module. This allows CPU-bound and memory-intensive tasks to execute with the speed of a native application, directly addressing the need for processing large datasets efficiently.

#### **Frameworks & Libraries**
- **Python Stack**
  - **FastAPI:** A modern, high-performance web framework for building APIs. Its asynchronous support is critical for handling I/O-bound operations like network requests and database calls without blocking. Automatic generation of interactive OpenAPI documentation is a significant plus.
  - **PyO3:** The foundational library for creating Rust bindings for Python. It enables seamless, low-overhead communication between the Python interpreter and the compiled Rust code, forming the bridge of our hybrid architecture.
  - **Celery:** A distributed task queue for running asynchronous background jobs. This is essential for offloading long-running file processing tasks from the API, ensuring the user interface remains responsive.
  - **Polars:** A blazingly fast DataFrame library written in Rust. It is the natural choice for any data manipulation done in the Python layer, offering a significant performance advantage over Pandas and integrating well with the Rust core.
- **Rust Stack**
  - **Rayon:** A data-parallelism library for Rust. It makes it easy to convert sequential computations into parallel ones, fully leveraging multi-core processors to speed up data processing.
  - **Tokio:** An asynchronous runtime for Rust, essential for building high-performance, non-blocking I/O operations when reading from or writing to object storage or other network resources.
  - **Serde:** A powerful framework for efficiently serializing and deserializing Rust data structures to and from formats like JSON, BSON, and others.

#### **Databases & Storage**
- **Primary Database: PostgreSQL (v15+)**
  - **Rationale:** A powerful, open-source object-relational database system known for its reliability, feature robustness, and extensibility. It will store user data, job metadata, application state, and configuration. Its support for advanced data types like JSONB is ideal for storing flexible metadata associated with processing jobs.
- **File Storage: Object Storage (AWS S3, Google Cloud Storage, or MinIO)**
  - **Rationale:** For storing large datasets, object storage is non-negotiable for scalability and durability. It decouples file storage from the application servers, allowing both to scale independently. Using presigned URLs for uploads/downloads will improve performance and security by offloading bandwidth from the API server. MinIO is an excellent self-hosted, S3-compatible alternative for development or on-premise deployments.
- **Cache & Message Broker: Redis (v7+)**
  - **Rationale:** Redis will serve a dual purpose: as a fast, in-memory cache for frequently accessed data and as the message broker for Celery. Its high performance is crucial for maintaining a low-latency task queue.

#### **Infrastructure & Deployment**
- **Containerization: Docker & Docker Compose**
  - **Rationale:** Docker will be used to containerize the Python API, Rust engine (within the Python container), and background workers. This ensures a consistent and reproducible environment across development, testing, and production. Docker Compose will orchestrate the multi-container setup for local development.
- **Orchestration: Kubernetes (K8s)**
  - **Rationale:** For production deployments, Kubernetes is the industry standard for automating the deployment, scaling, and management of containerized applications. It will allow us to independently scale the API and the processing workers based on load.
- **Cloud Provider: AWS / GCP / Azure**
  - **Rationale:** A major cloud provider offers the managed services (Kubernetes, PostgreSQL, Object Storage, Redis) needed to run the application reliably and scalably, reducing operational overhead.
- **CI/CD: GitHub Actions or GitLab CI**
  - **Rationale:** A robust CI/CD pipeline is essential for automation and quality assurance. The pipeline will lint, test, build a multi-stage Docker image (compiling Rust first, then adding it to the Python image), and deploy the application to staging and production environments.

### Architecture Overview

#### **System Design Pattern**
- **Hybrid Monolith with Asynchronous Task Processing**
  - **Rationale:** The application starts as a "majestic monolith" where the core API is a single deployable unit, reducing initial complexity. However, it's designed for scalability from the ground up by decoupling all heavy computation into an asynchronous task queue. This pattern provides a clear path to evolve into a microservices architecture if and when the need arises, by splitting the workers or API components into separate services.

#### **Components & Data Flow**
1.  **UI (React/Vue.js):** The user-facing single-page application where users upload files and manage processing jobs.
2.  **API Gateway (e.g., Nginx, Traefik):** The entry point for all incoming traffic. Handles SSL termination, load balancing, and routing requests to the FastAPI backend.
3.  **Python API (FastAPI):**
    - Handles user authentication (e.g., using JWT).
    - Provides REST endpoints for managing jobs.
    - When a job is initiated, it generates a presigned URL for the user to upload the file directly to Object Storage.
    - After upload confirmation, it creates a job entry in PostgreSQL and dispatches a task to the Celery queue.
4.  **Message Broker (Redis):** Holds the queue of processing tasks, decoupling the API from the workers.
5.  **Processing Workers (Celery):**
    - Python processes that listen for tasks on the queue.
    - Upon receiving a task, the worker invokes the **Rust Engine**.
    - The worker manages the overall job lifecycle, updating the status in PostgreSQL (e.g., `RUNNING`, `COMPLETED`, `FAILED`).
6.  **Rust Engine (PyO3 Module):**
    - A high-performance library called directly from the Python worker.
    - Streams the input file from Object Storage.
    - Performs the CPU-bound data transformations in memory.
    - Streams the processed output back to a new location in Object Storage.
7.  **Database (PostgreSQL):** The source of truth for all metadata, including user accounts, job definitions, and status.
8.  **Object Storage (S3/MinIO):** Stores all raw and processed file data.

**Data Flow (Example: CSV Filtering)**
1.  User clicks "Upload" in the UI.
2.  UI requests a presigned upload URL from the FastAPI API.
3.  UI uploads the large CSV file directly to the provided S3 URL.
4.  On successful upload, the UI calls the `/jobs` endpoint with the S3 file path and processing parameters (e.g., filter `country == "India"`).
5.  FastAPI creates a job in PostgreSQL with status `PENDING` and pushes a task to Celery.
6.  A Celery worker picks up the task, reads the job details, and calls the Rust function `process_csv(s3_path, params)` via PyO3.
7.  The Rust engine streams the CSV from S3, applies the filter using its parallel processing capabilities, and streams the resulting data to a new file in S3.
8.  Once finished, the worker updates the job status in PostgreSQL to `COMPLETED` and stores the output file path.
9.  The UI, which has been polling the `/jobs/{id}` endpoint, sees the `COMPLETED` status and displays a download link to the user.

#### **Integration & APIs**
- **Primary API:** A **RESTful API** served by FastAPI. It will be self-documented via OpenAPI/Swagger UI, providing a clear contract for the frontend and any potential third-party integrations.
- **Internal Integration:** The integration between Python and Rust will be via a direct **Foreign Function Interface (FFI)** managed by PyO3. This is not a network call but a highly efficient in-process function call, minimizing latency between the orchestrator and the engine.

---

## Requirements Documentation

### Functional Requirements

-   **FR1: Secure Multi-User File Management:** Users must be able to register, log in, and only access their own files and processing jobs.
-   **FR2: Large Dataset Upload:** The system must support uploading files up to 50 GB via the browser, without tying up API server resources.
-   **FR3: Configurable Processing Pipeline:** Users can define a series of processing steps to be applied to a dataset (e.g., filter, aggregate, transform columns, change format from CSV to Parquet).
-   **FR4: Asynchronous Job Execution & Monitoring:** All processing jobs run in the background. The UI must provide a real-time view of job status (Pending, Running, Succeeded, Failed) and logs.
-   **FR5: Results Download:** Users can download the resulting files once a job is complete.

#### **Sample User Stories**
-   **As a Data Analyst,** I want to upload a 10 GB log file and filter out all lines that do not contain the word "ERROR", so that I can quickly isolate relevant information.
-   **As a Data Scientist,** I want to convert a large CSV dataset into the Parquet format to significantly speed up my data loading times in my analytics environment.
-   **As an Administrator,** I want to view a dashboard of all running jobs, system resource usage, and error rates, so I can monitor the health of the platform.

### Non-Functional Requirements

-   **Performance:**
    -   API response time for metadata operations: < 150ms.
    -   Throughput: Process a 1 GB standard CSV file (e.g., filtering and selecting columns) in under 45 seconds on standard compute instances.
-   **Scalability:**
    -   The pool of processing workers must autoscale horizontally based on the length of the task queue.
    -   The system should be designed to handle over 100 concurrent processing jobs.
-   **Reliability & Availability:**
    -   Target 99.9% uptime for the API.
    -   Job processing should be fault-tolerant. If a worker crashes, the job should be requeued and retried automatically up to a configured limit.
-   **Security:**
    -   All data encrypted in transit (TLS 1.3) and at rest (using storage provider's encryption).
    -   Authentication via JWT (JSON Web Tokens).
    -   Implement strict Role-Based Access Control (RBAC) to ensure data tenancy.
    -   Regularly scan dependencies for vulnerabilities (`cargo audit`, `pip-audit`).
-   **Monitoring & Observability:**
    -   **Metrics:** Instrument the application with Prometheus to track API latency, error rates, queue depth, and job execution times.
    -   **Logging:** Implement structured logging (e.g., JSON) and forward logs to a centralized service like Loki or ELK Stack.
    -   **Alerting:** Configure alerts (via Alertmanager) for critical conditions like high failure rates, long queue waits, or high resource saturation.

### Technical Constraints

-   **Mandatory Technologies:** The core backend must be built with Python, and the high-performance processing components must be built with Rust.
-   **Initial Budget:** The architecture should be cost-effective on the cloud, leveraging auto-scaling and spot instances for workers where possible.
-   **Time-to-Market:** An MVP focusing on a single file type (CSV) and a limited set of transformations should be targeted for release within 3-4 months.

---

## Implementation Recommendations

### Development Approach

-   **Methodology: Scrum**
    -   Work will be organized into 2-week sprints. Each sprint will aim to deliver a potentially shippable increment of functionality. This agile approach allows for flexibility, continuous feedback, and iterative improvement.
-   **Testing Practices:**
    -   **Unit Tests:** Each function in both Rust (`cargo test`) and Python (`pytest`) will have comprehensive unit tests.
    -   **Integration Tests:** Test the interaction between components, especially the Python-to-Rust boundary and the API-to-worker flow.
    -   **End-to-End (E2E) Tests:** Use a framework like **Playwright** or **Cypress** to simulate user journeys from the UI through the entire backend stack.
    -   **CI-Driven Testing:** All tests must pass in the CI pipeline before a merge to the `main` branch is allowed.
-   **CI/CD Design (GitHub Actions):**
    1.  **On Pull Request:**
        -   Run linters (`ruff`, `black` for Python; `clippy`, `rustfmt` for Rust).
        -   Run all unit and integration tests for both languages.
        -   Build the Rust wheel using `maturin build --release`.
    2.  **On Merge to `main`:**
        -   All previous steps, plus:
        -   Build a multi-stage Docker image that incorporates the compiled Rust wheel.
        -   Push the tagged image to a container registry (e.g., AWS ECR).
        -   Trigger a deployment to the staging environment using Helm or Kustomize.
    3.  **On Git Tag (e.g., `v1.2.0`):**
        -   Trigger a deployment to the production environment.

### Risk Assessment

-   **Risk 1: Python/Rust FFI Complexity**
    -   **Description:** Managing the Foreign Function Interface (FFI) boundary, especially with complex data types, error handling, and avoiding memory leaks, can be challenging.
    -   **Mitigation:**
        1.  Strictly use **PyO3** to manage all FFI boilerplate and safety.
        2.  Establish clear patterns for error propagation (e.g., converting Rust `Result<T, E>` into Python exceptions).
        3.  Create a "spike" (a time-boxed investigation) early in the project to prototype the most complex data exchange expected between Python and Rust.
-   **Risk 2: Performance Bottlenecks Outside Rust**
    -   **Description:** The Rust engine may be incredibly fast, but the overall system performance could be limited by slow database queries, network I/O to object storage, or inefficient Python orchestration logic.
    -   **Mitigation:**
        1.  Implement distributed tracing (e.g., using OpenTelemetry) from day one to visualize the entire request lifecycle.
        2.  Use asynchronous libraries (`aiohttp`, `aiobotocore`) for all network I/O in the Python layer.
        3.  Profile the application under realistic load to identify and optimize the true bottlenecks, wherever they may be.
-   **Alternate Technologies:**
    -   **gRPC instead of PyO3/FFI:**
        -   **Pros:** True service decoupling, language-agnostic, independent scaling of Python and Rust services.
        -   **Cons:** Introduces network latency and serialization overhead for every call, significantly higher than FFI. More complex deployment and service discovery. Not ideal for the tightly-coupled, high-throughput use case here.

---

## Getting Started

### Prerequisites

-   **Local Machine:** Python 3.11+, Rust toolchain (installed via `rustup`), Docker, and Docker Compose.
-   **Python Tools:** `pip install "poetry>=1.2"` or `pip install "pdm>=2.0"`. `maturin` for building the Rust extension.
-   **Frontend Tools:** Node.js v18+ and `npm` or `yarn`.
-   **Required Skills:** Proficiency in Python (FastAPI), foundational knowledge of Rust, and experience with Docker.

### Project Structure

A monorepo structure is recommended to simplify dependency management and cross-language development.

```
karyaksham/
├── .github/workflows/         # CI/CD pipeline definitions
├── backend/                   # Python application
│   ├── karyaksham_api/        # FastAPI application source
│   │   ├── api/               # API endpoint routers
│   │   ├── core/              # Configuration, settings
│   │   ├── crud/              # Database interaction logic
│   │   └── schemas/           # Pydantic schemas
│   ├── karyaksham_workers/    # Celery worker definitions
│   └── tests/                 # Python tests
├── rust_engine/               # Rust processing engine crate
│   ├── src/
│   │   └── lib.rs             # Main library code exposed via PyO3
│   └── Cargo.toml             # Rust manifest
├── frontend/                  # React/Vue frontend application
├── .env.example               # Template for environment variables
├── docker-compose.yml         # Local multi-container development
├── Dockerfile.api             # Dockerfile for the API and workers
└── pyproject.toml             # Python project metadata and dependencies
```

### Configuration

-   **Environment Variables:** Use a `.env` file for local development. In production, these should be injected by the orchestration platform (Kubernetes) from a secure secrets store. Pydantic's `BaseSettings` can be used to load and validate configuration.

    ```dotenv
    # .env.example
    # Application
    ENVIRONMENT=development
    SECRET_KEY=a_very_secret_key_for_jwt

    # PostgreSQL Database
    POSTGRES_SERVER=db
    POSTGRES_USER=karyaksham
    POSTGRES_PASSWORD=password
    POSTGRES_DB=karyakshamdb

    # Redis Broker & Cache
    REDIS_HOST=redis
    REDIS_PORT=6379

    # Object Storage (MinIO for local dev)
    OBJECT_STORAGE_ENDPOINT=http://minio:9000
    OBJECT_STORAGE_ACCESS_KEY=minioadmin
    OBJECT_STORAGE_SECRET_KEY=minioadmin
    OBJECT_STORAGE_BUCKET=karyaksham-data
    ```

-   **Secrets Management:** In production, never use `.env` files. Integrate with a dedicated secrets manager like **HashiCorp Vault**, **AWS Secrets Manager**, or **Google Secret Manager**. These can be securely mounted into the Kubernetes pods.