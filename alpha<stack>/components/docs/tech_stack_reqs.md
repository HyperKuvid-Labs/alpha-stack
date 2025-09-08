# Technical Stack Documentation

### Project Title

**Project Sanchay**

*(Sanchay is a Hindi word meaning "collection" or "storage," reflecting the application's core purpose of handling and processing collections of files and data.)*

---

### Core Technologies

#### **Programming Languages**

*   **Python (v3.10+)**
    *   **Justification:** Python will serve as the primary language for the application's user interface, business logic, and orchestration layer. Its rich ecosystem of libraries, rapid development capabilities, and ease of integration make it ideal for building the user-facing components and managing high-level workflows. We will leverage `asyncio` for concurrent I/O-bound tasks within the Python layer.

*   **Rust (v1.65+ - Stable)**
    *   **Justification:** Rust will be used to build the high-performance core engine for all file/folder processing tasks. Its key advantages are memory safety without a garbage collector, fearless concurrency, and C-level performance. This makes it the perfect choice for CPU-bound tasks like file parsing, data manipulation, and parallel directory traversal, ensuring the application can handle massive datasets efficiently and safely.

#### **Frameworks & Libraries**

*   **Python Frontend/UI**
    *   **PySide6 (v6.4+)**: A modern, feature-rich library for creating native desktop applications with Qt.
    *   **Justification:** Provides a professional, cross-platform user interface that feels native to the host OS. Its LGPL license is permissive for commercial applications. It offers a robust set of widgets and tools for building a user-friendly and responsive interface.

*   **Python-Rust Integration**
    *   **PyO3 (v0.18+)** with **Maturin**: The premier framework for creating Python extension modules in Rust.
    *   **Justification:** `PyO3` provides seamless and efficient bindings between Python and Rust, allowing Python code to call Rust functions with minimal overhead. `Maturin` is a build tool that manages the entire process of compiling the Rust code and packaging it into a standard Python wheel, simplifying distribution and installation.

*   **Rust Core Engine**
    *   **Rayon**: A data-parallelism library for Rust.
    *   **Justification:** Effortlessly converts sequential computations (like iterating over files) into parallel ones, taking full advantage of multi-core processors to speed up processing.
    *   **Serde**: A framework for serializing and deserializing Rust data structures efficiently.
    *   **Justification:** Essential for converting data between Rust structs and formats like JSON or binary formats, which might be used for configuration, caching, or inter-process communication.
    *   **Walkdir**: A crate for efficiently walking directory trees.
    *   **Justification:** A highly optimized alternative to the standard library's directory iterator, providing better performance and more control when scanning large and deep folder structures.
    *   **Tokio** (Optional): An asynchronous runtime for Rust.
    *   **Justification:** While `Rayon` is for CPU-bound parallelism, `Tokio` would be used if the Rust core needs to perform highly concurrent, non-blocking I/O operations (e.g., interacting with many network services or files simultaneously).

#### **Databases & Storage**

*   **Primary Database: SQLite**
    *   **Justification:** For the initial desktop-focused application, SQLite is a perfect choice. It's a serverless, self-contained, and highly reliable SQL database engine. It requires zero configuration and stores the database in a single file, making the application portable and easy to manage. It's more than capable of handling metadata for millions of files.

*   **Scalable Database Option: PostgreSQL (v15+)**
    *   **Justification:** If the application evolves to a multi-user, client-server model, PostgreSQL offers robust performance, scalability, and advanced features. The application logic should be written using an ORM like `SQLAlchemy` (Python) or `Diesel` (Rust) to allow for a smooth transition from SQLite to PostgreSQL.

*   **Object Storage: AWS S3 / MinIO**
    *   **Justification:** For cloud-native scalability, the application should be able to process files directly from object storage. This decouples the processing engine from the local filesystem, enabling it to run on ephemeral cloud compute instances and handle petabyte-scale datasets.

#### **Infrastructure & Deployment**

*   **Containerization: Docker**
    *   **Justification:** Docker will be used to create consistent, reproducible build and runtime environments. A multi-stage `Dockerfile` will be used to first compile the Rust core in a Rust-specific container, then copy the compiled artifacts into a lightweight Python container, resulting in an optimized final image.

*   **Cloud Provider: AWS (as a primary example)**
    *   **Justification:** AWS provides a mature and comprehensive suite of services. For a scalable deployment, we would use:
        *   **Amazon EC2/Fargate:** For running the application containers.
        *   **Amazon S3:** For scalable and durable object storage.
        *   **Amazon RDS for PostgreSQL:** For a managed, scalable database service.

*   **CI/CD Pipeline: GitHub Actions**
    *   **Justification:** Tightly integrated with GitHub, providing a simple yet powerful way to automate building, testing, and deployment. The pipeline will be configured to build and test both the Rust and Python code, package the application, and deploy it to a target environment.

---

### Architecture Overview

#### **System Design Pattern**

**Modular Monolith with a Native Extension Core**

The application will be designed as a single deployable unit (a monolith) but with strong internal boundaries separating its key responsibilities. This approach simplifies development and deployment initially while allowing for future separation into microservices if needed. The core of the architecture is the Rust engine, which acts as a compiled native extension, ensuring that performance-critical code is cleanly isolated.

#### **Components & Data Flow**

1.  **User Interface (PySide6)**: The user interacts with the GUI to specify target directories, configure processing jobs, and view results.
2.  **Application Logic (Python)**: This layer acts as the orchestrator. It receives commands from the UI, manages job queues, and prepares data to be sent to the core engine. It uses `asyncio` to remain responsive while waiting for long-running tasks.
3.  **Python-Rust Bridge (PyO3)**: This is the interface layer where Python objects are converted into Rust data structures and function calls are made to the compiled Rust library (`.so` or `.pyd` file).
4.  **Rust Core Engine (Rust)**: This is the workhorse. It receives instructions and data (e.g., a root path), and uses `Rayon` and `walkdir` to perform parallel processing on the filesystem. It is completely stateless and performs computations without being affected by Python's Global Interpreter Lock (GIL).
5.  **Metadata Store (SQLite)**: Both the Rust engine (via a crate like `rusqlite`) and the Python layer (via `sqlite3` module) can interact with the SQLite database to store and retrieve file metadata, job status, and processing results.

**Data Flow Example (File Duplication Check):**
*   User selects a folder `/path/to/data` in the UI.
*   The Python application logic receives this path.
*   Python calls the Rust function `find_duplicates("/path/to/data")` via the `PyO3` bridge.
*   The Rust Core Engine spawns multiple threads using `Rayon` to walk the directory, calculate file hashes in parallel, and identify duplicates.
*   The results (a list of duplicate files) are returned to Python as a Python object.
*   The Python layer displays the results in the UI and stores them in the SQLite database for history.

#### **Integration & APIs**

*   **Internal API:** The primary "API" is the function boundary between Python and Rust defined using `PyO3`. This API will be strongly typed and well-documented within the codebase.
*   **External API (Optional): REST API via FastAPI**
    *   For headless operation or integration with other services, a `FastAPI` server can be wrapped around the Python application logic. This would expose endpoints like `POST /jobs` to start a new processing task and `GET /jobs/{job_id}` to check its status, allowing the powerful Rust core to be controlled programmatically.

---

## Requirements Documentation

### Functional Requirements

*   **FR1: Directory Scanning:** The system shall allow a user to select a directory on their local filesystem or a specified cloud storage path.
*   **FR2: Parallel Processing:** The system shall process files within the selected directory in parallel to maximize throughput. Initial processing tasks will include checksum generation, metadata extraction, and file counting.
*   **FR3: Job Management:** The system shall provide a real-time view of ongoing processing jobs, including progress indicators (e.g., percentage complete, files processed per second).
*   **FR4: Results Visualization:** The system shall display the results of a processing job in a clear, user-friendly format (e.g., a table of duplicate files, a summary of file types).
*   **FR5: Headless Operation:** The system must be executable via a command-line interface (CLI) for scripting and automation, without launching the GUI.

#### Sample User Stories

1.  **As a Data Analyst,** I want to select a folder containing 10 million log files so that I can quickly generate a metadata report (file size, creation date) for all of them.
2.  **As a Photographer,** I want to scan my entire photo archive to find and list all duplicate images based on their content hash, so that I can free up disk space.
3.  **As a System Administrator,** I want to run a nightly job from a script that scans a network drive for files larger than 1 GB, so that I can monitor storage usage without manual intervention.

### Non-Functional Requirements

*   **Performance:**
    *   The system must be able to scan and checksum at least 500,000 small files (<1MB) per minute on a standard quad-core machine.
    *   UI must remain responsive and not freeze during intensive backend processing.
*   **Security:**
    *   File path inputs must be sanitized to prevent path traversal vulnerabilities.
    *   The application must not require elevated (root/administrator) privileges for standard operation.
    *   Sensitive configurations (e.g., cloud credentials) must be stored securely, not in plaintext.
*   **Scalability & Reliability:**
    *   The core Rust engine must be architected to scale linearly with the number of available CPU cores.
    *   The application must gracefully handle I/O errors (e.g., permission denied, file not found) without crashing.
    *   The system should handle files and directory structures that exceed available RAM by streaming data rather than loading entire files into memory where possible.
*   **Monitoring & Alerting:**
    *   The application must produce structured logs (e.g., JSON format) for both Python and Rust components.
    *   Key performance metrics (e.g., processing duration, files per second, memory usage) should be logged for analysis.

### Technical Constraints

*   **Core Technology Stack:** The use of Python for the application layer and Rust for the performance-critical core is mandatory.
*   **Initial Platform:** The initial release must support Windows 10/11, macOS, and a mainstream Linux distribution (e.g., Ubuntu 22.04).
*   **Resource Limitations:** The development team is small (2-4 engineers). The chosen architecture and tools should prioritize developer productivity and ease of maintenance.
*   **Time to Market:** An initial Minimum Viable Product (MVP) should be deliverable within 3-4 months.

---

## Implementation Recommendations

### Development Approach

*   **Methodology: Agile (Scrum)**
    *   Work will be organized into 2-week sprints. Each sprint will aim to deliver a small, demonstrable increment of functionality. This allows for continuous feedback and adaptation.
    *   **Sprint Zero:** Focus on setting up the project structure, CI/CD pipeline, and a basic "hello world" integration between Python and Rust.
*   **Testing Practices:**
    *   **Rust Unit Tests:** Each function in the Rust core will be accompanied by unit tests using `cargo test`.
    *   **Python Unit Tests:** Business logic in the Python layer will be tested using `pytest`. Mocks will be used to isolate the Python code from the Rust extension and the UI.
    *   **Integration Tests:** These will test the full flow from the Python layer through the Rust core and back, verifying the `PyO3` bridge and data conversions.
    *   **End-to-End (E2E) Tests:** Automated UI tests will be written to simulate user interactions and validate the final behavior.

### CI/CD Design

A GitHub Actions workflow will be triggered on every push to the `main` branch or on pull request creation.

1.  **Lint & Format:** Run `black` and `isort` on Python code; run `cargo fmt` and `clippy` on Rust code.
2.  **Test:**
    *   Run `cargo test` in the Rust crate directory.
    *   Run `pytest` in the Python application directory.
3.  **Build:**
    *   Use `maturin build --release` to compile the Rust core and create a platform-specific Python wheel.
4.  **Package:**
    *   Use a tool like `PyInstaller` or `cx_Freeze` to bundle the Python application, the Rust wheel, and all dependencies into a standalone executable for each target OS (Windows, macOS, Linux).
5.  **Release:**
    *   On git tag, automatically create a GitHub Release and upload the packaged executables as artifacts.

### Risk Assessment

*   **Risk 1: Complexity of Python-Rust Integration**
    *   **Description:** Passing complex data structures or managing object lifetimes between Python and Rust can be challenging and error-prone.
    *   **Mitigation:**
        *   Use simple, serializable data types for the boundary where possible.
        *   Leverage `PyO3`'s features for lifetime management carefully.
        *   Write extensive integration tests covering all boundary calls.
        *   Consider using Apache Arrow for transferring large, tabular datasets with zero-copy overhead.

*   **Risk 2: Cross-Platform Build and Distribution**
    *   **Description:** Creating distributable application bundles for Windows, macOS, and Linux can be complex, especially with a compiled native component.
    *   **Mitigation:**
        *   Rely heavily on `maturin`, which is designed to solve this problem.
        *   Use GitHub Actions with runners for each target OS to automate the builds in a clean environment.
        *   Start with a minimal application to iron out the packaging and distribution pipeline early.

*   **Risk 3: GIL Contention in the Orchestration Layer**
    *   **Description:** Even though the core logic is in Rust, a poorly written Python orchestration layer could become a bottleneck due to the Global Interpreter Lock (GIL).
    *   **Mitigation:**
        *   Ensure all long-running, CPU-bound work is delegated to a single call into the Rust engine.
        *   Use Python's `asyncio` for I/O-bound tasks (like updating the UI or writing to a network socket) so the application remains responsive.
        *   If multiple Rust tasks must be run concurrently *from Python*, use `multiprocessing` to spawn separate processes, each with its own Python interpreter and its own instance of the Rust extension.

#### Alternate Technologies

*   **UI Framework: Tauri**
    *   **Description:** An alternative to PySide6. Tauri allows you to build a UI with web technologies (HTML, CSS, JavaScript) but with a Rust backend.
    *   **Pros:** Modern web-based UI, potentially smaller executable size, deep integration with the Rust ecosystem.
    *   **Cons:** Would remove Python from the stack, which contradicts the user request. However, it's a powerful option if the Python requirement were to be relaxed.

---

## Getting Started

### Prerequisites

*   **Python 3.10+** and `pip`
*   **Rust Toolchain:** Installed via `rustup` (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
*   **Maturin:** `pip install maturin`
*   **Python Virtual Environment Tool:** `pip install virtualenv`
*   **Git**

### Project Structure

A monorepo structure is recommended to keep the Python and Rust code together.

```
/project-sanchay/
├── .github/workflows/         # CI/CD pipeline definitions
│   └── ci.yml
├── .gitignore
├── pyproject.toml             # Project metadata, dependencies, and maturin config
├── README.md
│
├── sanchay_core/              # The Rust crate
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs             # Main library file with PyO3 bindings
│       └── ...                # Other Rust modules
│
└── app/                       # The Python application
    ├── __main__.py            # Main entry point
    ├── main_window.py         # PySide6 UI code
    ├── logic.py               # Application orchestration logic
    └── ...                    # Other Python modules
```

**`pyproject.toml` (Partial Example):**

```toml
[build-system]
requires = ["maturin>=0.14,<0.15"]
build-backend = "maturin"

[project]
name = "sanchay"
requires-python = ">=3.10"
classifiers = [
    "Programming Language :: Rust",
    "Programming Language :: Python :: Implementation :: CPython",
]

[tool.maturin]
features = ["pyo3/extension-module"]
```

### Configuration

*   **Environment Variables:** Application configuration (e.g., log level, database path) should be managed via environment variables.
*   **Secrets Handling:** For production deployments involving cloud services, use a dedicated secrets manager like AWS Secrets Manager or HashiCorp Vault. For local development, use a `.env` file loaded at runtime by a library like `python-dotenv`. The `.env` file should be included in `.gitignore`.

**Example `.env` file:**
```
# .env
LOG_LEVEL=INFO
DATABASE_PATH=./sanchay_metadata.db
```