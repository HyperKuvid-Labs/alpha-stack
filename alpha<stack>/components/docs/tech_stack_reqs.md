# Technical Stack Documentation

### Project Title
**Pravah: High-Performance File & Data Processing Engine**

*(Pravah, a Sanskrit word for "flow" or "stream," reflects the project's goal of creating a fast and efficient data processing pipeline.)*

### Core Technologies

#### **Programming Languages**
*   **Python (3.11+)**
    *   **Justification:** Python will serve as the primary language for the application's high-level logic, API layer, and user interface. Its extensive ecosystem of libraries (e.g., for web frameworks, data science), rapid development cycle, and ease of use make it ideal for orchestrating complex workflows and building user-facing components.
*   **Rust (Latest Stable Version)**
    *   **Justification:** Rust will be used to build the core processing engine. Its key advantages are performance comparable to C/C++, guaranteed memory safety without a garbage collector, and fearless concurrency. This makes it the perfect choice for CPU-bound and I/O-bound tasks like parsing large files, complex computations, and parallel data manipulation across multiple cores, ensuring maximum efficiency and reliability.

#### **Frameworks & Libraries**
*   **Python Stack**
    *   **FastAPI (v0.100.0+):** A modern, high-performance web framework for building the REST API.
        *   **Why:** Its asynchronous nature (built on Starlette and Uvicorn) integrates perfectly with I/O-bound tasks. It offers automatic data validation via Pydantic and generates interactive API documentation (Swagger UI/OpenAPI), accelerating development and improving maintainability.
    *   **PyO3 (v0.20.0+):** The crucial bindings library to create a seamless bridge between Python and Rust.
        *   **Why:** It allows us to compile the Rust code into a Python module that can be imported and used directly, enabling Python to call high-performance Rust functions with minimal overhead.
    *   **Streamlit or React/Next.js (for UI):**
        *   **Streamlit:** Recommended for a rapid, data-centric internal tool or dashboard. It allows building a user-friendly web UI with pure Python.
        *   **React/Next.js:** Recommended for a full-fledged, highly interactive, customer-facing application. This provides a more robust and customizable frontend experience.
    *   **Typer (v0.9.0+):** For building a powerful and user-friendly Command Line Interface (CLI).
        *   **Why:** Based on FastAPI's principles, it simplifies CLI development with type hints and is excellent for scripting and automation use cases.

*   **Rust Stack (Core Engine)**
    *   **Tokio (v1.28.0+):** An asynchronous runtime for Rust.
        *   **Why:** Essential for building high-performance, non-blocking I/O operations. It will allow the engine to handle thousands of concurrent file operations (reading, writing, network requests) efficiently.
    *   **Rayon (v1.7.0+):** A data-parallelism library.
        *   **Why:** It makes it trivial to convert sequential computations (e.g., processing items in a list) into parallel ones, automatically leveraging all available CPU cores to speed up CPU-bound tasks.
    *   **Serde (v1.0.0+):** A framework for serializing and deserializing Rust data structures.
        *   **Why:** Extremely fast and versatile for handling data formats like JSON, Bincode, and others, which is crucial for reading configuration, parsing structured files, and communicating between components.
    *   **walkdir (v2.3.0+):** A crate for efficient recursive directory traversal.
        *   **Why:** Optimized for walking large directory trees, it's more performant than standard library equivalents and offers fine-grained control over the traversal process.

#### **Databases & Storage**
*   **Primary Storage: Filesystem / Object Storage (Amazon S3, MinIO)**
    *   **Rationale:** The application's core purpose is to process files. For standalone deployments, it will operate on a local or network filesystem. For cloud-native, scalable deployments, using an object store like **Amazon S3** (or its open-source equivalent, **MinIO**) is recommended. This provides virtually unlimited scalability, durability, and decouples storage from compute.
*   **Metadata & Job Queue: PostgreSQL (v15+)**
    *   **Rationale:** A relational database is ideal for storing structured metadata about files, tracking the status of processing jobs, managing user accounts, and storing application configuration. **PostgreSQL** is chosen for its robustness, reliability, and powerful features like JSONB support and transactional integrity (ACID compliance), which are critical for a reliable job processing system. For simpler, embedded use cases, **SQLite** could be a lightweight alternative.

#### **Infrastructure & Deployment**
*   **Cloud Provider: AWS (Recommended)**
    *   **Rationale:** AWS offers a mature ecosystem of managed services that align perfectly with this project's needs, including S3 for object storage, EC2/Fargate for compute, RDS for PostgreSQL, and a robust IAM for security.
*   **Containerization: Docker & Docker Compose**
    *   **Rationale:** Docker will be used to containerize the Python application and its Rust core, ensuring a consistent and reproducible environment from development to production. `docker-compose` will orchestrate multi-container setups locally (e.g., app + database).
*   **Orchestration: Kubernetes (e.g., AWS EKS)**
    *   **Rationale:** For production deployments requiring high availability and auto-scaling, Kubernetes is the de-facto standard. It allows us to manage containerized workloads, scale processing nodes based on demand, and perform rolling updates with zero downtime.
*   **CI/CD Pipeline: GitHub Actions**
    *   **Rationale:** A CI/CD pipeline integrated directly with the source code repository is essential for automation. GitHub Actions provides a simple yet powerful way to define workflows for testing, building, and deploying the application on every code change.

---

## Architecture Overview

#### **System Design Pattern**
*   **Modular Monolith with a Core-Plugin Architecture:** The system is designed as a single deployable unit (a monolith) for simplicity in initial development and deployment. However, it's internally structured with high modularity. The high-performance Rust engine acts as a "core plugin" to the main Python application. This architecture allows the performance-critical component (Rust) to be developed and optimized independently of the application logic (Python), offering a clear separation of concerns and a straightforward path to potentially extracting it into a separate microservice in the future if needed.

#### **Components & Data Flow**
1.  **User Interface (CLI / Web UI):** The user initiates a job, e.g., "Process all `.csv` files in directory X."
2.  **API Layer (FastAPI):** The request is received by the FastAPI backend. It validates the input parameters (e.g., file path, processing options) using Pydantic models.
3.  **Job Orchestrator (Python Logic):** A new job is created and its initial state (`PENDING`) is persisted in the PostgreSQL database. The job details are passed to the core processing logic.
4.  **Python-Rust Bridge (PyO3):** The Python orchestrator calls the main processing function in the compiled Rust library, passing the job parameters (e.g., directory path, configuration).
5.  **Rust Core Engine:**
    *   Uses `walkdir` and `tokio` to asynchronously and concurrently scan the target directory for files.
    *   For each file, it spawns a task. For CPU-bound processing on the file's content, it uses a `rayon` thread pool to parallelize the work across all available CPU cores.
    *   Progress and results are communicated back to the Python layer, either through callbacks or by returning a final summary.
6.  **Data Persistence:** The results are written to the specified destination (filesystem or S3), and the job status in PostgreSQL is updated to `COMPLETED` or `FAILED`.
7.  **Feedback to User:** The API layer returns a job ID to the user, who can then poll an endpoint to check the status and retrieve the results.




#### **Integration & APIs**
*   **Internal API (Python <> Rust):** A tightly-coupled, in-process API defined using `PyO3`. Data structures are shared using types that can be seamlessly converted between Python objects and Rust structs. This is optimized for performance, minimizing serialization overhead.
*   **External API (REST):** A public-facing REST API exposed via FastAPI. This will be the primary way for users and other services to interact with Pravah. It will follow OpenAPI standards and include endpoints for:
    *   `POST /jobs`: Create and start a new processing job.
    *   `GET /jobs/{job_id}`: Check the status and progress of a job.
    *   `GET /jobs/{job_id}/results`: Retrieve the results of a completed job.
    *   `GET /config`: View available processing configurations.

---

## Requirements Documentation

### Functional Requirements
*   **High-Speed Directory Traversal:** The system must be able to recursively scan directories containing millions of files and subdirectories with minimal latency.
*   **Parallel File Processing:** The system must process multiple files concurrently, leveraging all available system resources (CPU cores and I/O capacity).
*   **Configurable Processing Pipelines:** Users should be able to define simple pipelines or select predefined processing tasks (e.g., format conversion, data extraction, compression) via the API.
*   **Job Management & Status Tracking:** All operations must be treated as jobs that can be created, monitored, and queried for their status (e.g., pending, running, completed, failed).
*   **Support for Local and Cloud Storage:** The system must be able to read from and write to both local filesystems and S3-compatible object storage.

#### **Sample User Stories**
1.  **As a Data Scientist,** I want to submit a job to scan a directory containing 500,000 CSV files and extract the header row from each file, so that I can quickly analyze the schema of my dataset.
2.  **As a DevOps Engineer,** I want to use the CLI to run a daily job that finds all log files larger than 100MB in `/var/log` and compresses them, so that I can manage disk space automatically.
3.  **As a Web Developer,** I want to use the REST API to upload a ZIP file containing thousands of images, have the system extract them, resize them to a 1024x1024 thumbnail, and save them to an S3 bucket, so I can efficiently process user-uploaded content.

### Non-Functional Requirements
*   **Performance:**
    *   Directory scanning throughput: > 10,000 files/second on a standard SSD.
    *   API response time (for non-job--starting requests): < 150ms.
    *   CPU Utilization: The Rust engine should be able to saturate all available CPU cores during parallel processing tasks.
*   **Security:**
    *   **Access Control:** Implement role-based access control (RBAC) for API endpoints.
    *   **Secrets Management:** All sensitive credentials (DB passwords, API keys) must be loaded from environment variables or a secrets manager (e.g., AWS Secrets Manager), not hardcoded.
    *   **Input Validation:** Rigorously validate all inputs at the API boundary to prevent injection attacks and path traversal vulnerabilities.
    *   **Data Encryption:** Support encryption in transit (TLS) and at rest (using S3 server-side encryption).
*   **Scalability & Reliability:**
    *   **Horizontal Scalability:** The application should be stateless to allow for horizontal scaling. Multiple instances (containers) should be able to run concurrently, pulling jobs from the PostgreSQL queue.
    *   **Fault Tolerance:** A job failure should not bring down the entire system. The status should be logged, and other jobs should continue processing.
    *   **High Availability:** The system should be deployable in a multi-node configuration to ensure availability even if one node fails.
*   **Monitoring & Alerting:**
    *   **Metrics:** Expose key application metrics (e.g., jobs processed, error rates, processing duration) in a Prometheus-compatible format.
    *   **Logging:** Implement structured logging (e.g., JSON format) for all components to facilitate easier parsing and analysis.
    *   **Tracing:** Use OpenTelemetry to trace requests as they flow from the API through the Python and Rust layers, helping to pinpoint performance bottlenecks.

### Technical Constraints
*   **Core Technology Mandate:** The solution must use Python for high-level logic and Rust for the performance-critical processing engine.
*   **Initial Deployment:** The initial version should be deployable as a single Docker container for ease of use.
*   **Time-to-Market:** A Minimum Viable Product (MVP) with CLI and core processing capabilities should be targeted for delivery within a 3-month timeframe.

---

## Implementation Recommendations

### Development Approach
*   **Methodology: Scrum**
    *   Work will be organized into 2-week sprints. Each sprint will aim to deliver a small, vertical slice of functionality (e.g., from API endpoint to Rust implementation). This agile approach allows for iterative development, frequent feedback, and flexibility to adapt to changing requirements.
*   **Testing Practices:**
    *   **Rust Unit Tests (`cargo test`):** Each function in the Rust core must have corresponding unit tests to ensure correctness and prevent regressions.
    *   **Python Unit & Integration Tests (`pytest`):** The Python application logic, API endpoints, and the Python-Rust interface will be tested using `pytest`. Mocks will be used to isolate components.
    *   **End-to-End (E2E) Tests:** A small suite of E2E tests will simulate user workflows (e.g., submitting a job via the API and verifying the output in storage) using a tool like `pytest-httpserver` or by scripting against a running instance.
    *   **CI-Driven Testing:** All tests will be automatically executed in the CI pipeline for every commit and pull request.
*   **CI/CD Design (using GitHub Actions):**
    1.  **On Pull Request:**
        *   Lint Python code (`ruff`) and Rust code (`clippy`).
        *   Run all Python and Rust unit tests.
        *   Build the Rust wheel (`maturin`).
    2.  **On Merge to `main`:**
        *   All steps from the PR workflow.
        *   Build and tag the Docker image.
        *   Push the Docker image to a container registry (e.g., AWS ECR).
        *   (Optional) Automatically deploy the new image to a staging environment.
    3.  **On Git Tag (e.g., `v1.2.0`):**
        *   Trigger the deployment workflow to the production environment.

### Risk Assessment
*   **Risk 1: Performance Overhead at Python-Rust Boundary**
    *   **Description:** Frequent, small calls between Python and Rust can introduce significant overhead due to data marshalling.
    *   **Mitigation:** Design the Rust API to be "chunky" rather than "chatty." Pass large data collections (e.g., a list of all files to process) in a single call, and let Rust handle the internal looping and parallelism. Avoid callbacks from Rust to Python inside tight loops.
*   **Risk 2: Complexity of Hybrid Development Environment**
    *   **Description:** Developers will need to manage both Python and Rust toolchains, which can complicate the setup and build process.
    *   **Mitigation:**
        *   Use `maturin` to manage the Rust build and packaging as a standard Python wheel. This simplifies the Python side of development.
        *   Heavily script the development setup and build process using `Makefile` or `justfile`.
        *   Provide a `Dockerfile` for development that includes all necessary tools, creating a consistent environment for all team members.
*   **Risk 3: Memory Management for Very Large Files**
    *   **Description:** Loading entire large files into memory in Rust can lead to OOM (Out of Memory) errors, even without a garbage collector.
    *   **Mitigation:** Implement streaming processing. Use buffered readers (`std::io::BufReader`) in Rust to process large files chunk by chunk, ensuring memory usage remains low and constant regardless of file size.

#### **Alternate Technologies**
*   **Instead of Rust: Go or C++/Cython**
    *   **Go:**
        *   **Pros:** Excellent concurrency model (goroutines), simple syntax, fast compilation.
        *   **Cons:** Less fine-grained control over memory and performance compared to Rust. Interoperability with Python (CGo) is often considered more complex than PyO3.
    *   **C++/Cython:**
        *   **Pros:** The traditional choice for performant Python extensions. Cython simplifies the process.
        *   **Cons:** Lacks the built-in memory safety guarantees of Rust, making it more prone to bugs like segfaults and memory leaks. The modern tooling and package management in the Rust ecosystem are superior.

---

## Getting Started

### Prerequisites
*   **Developer Machine Setup:**
    *   Python 3.11+
    *   Rust toolchain (installed via `rustup.rs`)
    *   Docker and Docker Compose
    *   `make` or `just` (a convenient command runner)
*   **Required Skills:**
    *   Intermediate to Advanced Python.
    *   Basic to Intermediate Rust.
    *   Familiarity with Docker and REST APIs.

### Project Structure
A monorepo structure is recommended to keep the Python and Rust codebases together.

```
/pravah/
├── .github/workflows/          # CI/CD pipelines (e.g., ci.yml)
├── app/                        # Python application source
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entrypoint
│   ├── api/                    # API endpoint definitions
│   ├── core/                   # Core Python logic, job orchestration
│   └── config.py               # Pydantic settings
├── core_engine/                # Rust core engine (Cargo crate)
│   ├── Cargo.toml              # Rust dependencies and project settings
│   └── src/
│       └── lib.rs              # Main Rust library code (PyO3 module)
├── tests/
│   ├── test_api.py
│   └── test_integration.py
├── scripts/                    # Helper scripts (e.g., for deployment)
├── .env.template               # Template for environment variables
├── .gitignore
├── docker-compose.yml          # For local development (app + postgres)
├── Dockerfile                  # Multi-stage Dockerfile for production
├── pyproject.toml              # Python project metadata and dependencies (using Poetry/PDM)
└── README.md
```

### Configuration
*   **Environment Variables:** All configuration should be managed via environment variables. Create a `.env` file for local development (and add it to `.gitignore`).
*   **Secrets Handling:** Use a library like `pydantic-settings` in Python to automatically load configuration from `.env` files, system environment variables, or secrets files.
*   **Example `.env` file:**
    ```ini
    # Application Settings
    LOG_LEVEL=INFO

    # Database
    DATABASE_URL=postgresql://user:password@localhost:5432/pravah_db

    # S3 Storage (optional)
    AWS_ACCESS_KEY_ID=
    AWS_SECRET_ACCESS_KEY=
    S3_BUCKET_NAME=my-pravah-bucket
    S3_ENDPOINT_URL= # For MinIO
    ```
*   **Secrets in Production:** For production environments, these variables should be injected securely by the orchestrator (e.g., Kubernetes Secrets) or a dedicated secrets management tool (e.g., AWS Secrets Manager, HashiCorp Vault).