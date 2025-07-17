# Data Flow in VēgaFS

This document outlines the high-level data flow within the VēgaFS system, detailing how information moves between its primary components from initial request to final result storage. The architecture emphasizes a clear separation of concerns between the Python application layer and the high-performance Rust core.

## System Overview

VēgaFS is designed as a **Modular Monolith with a Core Library**. This means that while the application is deployed as a single unit, its internal structure segregates the high-level orchestration and API handling (Python) from the low-level, performance-critical data processing (Rust). Data flow is optimized for efficiency, especially across the Python-Rust boundary, leveraging `PyO3` for high-speed inter-language communication.

## Core Components and Their Roles in Data Flow

The primary components involved in the VēgaFS data flow are:

1.  **Client (Web UI / CLI):** The external interface through which users or automated systems interact with VēgaFS, initiating jobs and retrieving results.
2.  **API Layer (FastAPI):** The Python-based web service that receives HTTP requests, performs initial validation, handles authentication/authorization, and manages the lifecycle of processing jobs.
3.  **Orchestration Logic (Python):** The business logic component responsible for querying the database for pending jobs, preparing data for the Rust core, making calls to the core, and updating job status and results.
4.  **VēgaFS Rust Core (Shared Library):** The high-performance engine written in Rust. It performs the computationally intensive tasks such as parallel file traversal, data processing, and direct I/O operations on the underlying storage.
5.  **Data Storage & Cache:**
    *   **Primary Data Storage (File System / Object Storage):** The actual source and destination for files and data being processed (e.g., local disk, AWS S3, Google Cloud Storage).
    *   **PostgreSQL:** The persistent relational database used to store structured metadata about jobs, their status, parameters, and final processing results.
    *   **Redis:** An in-memory data store used for caching frequently accessed metadata or intermediate processing results to improve performance and reduce redundant computations.

## Data Flow Steps

The typical data flow for a processing job in VēgaFS proceeds through the following stages:

### 1. Request Initiation by Client

*   **Action:** A user or automated script submits a processing request (e.g., "Summarize directory `/data/project-x`", "Find and transform all `.csv` files") to the VēgaFS REST API or interacts via the Command-Line Interface (CLI).
*   **Data Transmitted:** Job parameters, target file paths/directories, desired operations, and any specific configuration options.

### 2. API Layer Processing and Job Creation

*   **Component:** FastAPI application (within `app/api`).
*   **Action:**
    *   Receives the incoming HTTP request.
    *   Validates and sanitizes all input parameters to prevent vulnerabilities (e.g., path traversal) and ensure data integrity.
    *   Authenticates and authorizes the requesting client.
    *   Creates a new job entry in the **PostgreSQL** database, typically with an initial `PENDING` status, and assigns a unique `job_id` for tracking.
    *   Returns the `job_id` to the client for asynchronous status monitoring.
*   **Data Transmitted:** Validated job request details to PostgreSQL.

### 3. Orchestration and Internal Call to Rust Core

*   **Component:** Python Orchestration Logic (within `app/core/processor.py`).
*   **Action:**
    *   The orchestrator continuously monitors the **PostgreSQL** database for jobs marked as `PENDING`.
    *   Upon detecting a `PENDING` job, it retrieves its parameters and prepares the necessary context.
    *   It then makes a direct, in-process function call to the VēgaFS Rust Core Library via the `PyO3` bindings. This is a high-speed, low-overhead Foreign Function Interface (FFI) call within the same process.
    *   The job status in PostgreSQL is updated to `PROCESSING`.
*   **Data Transmitted:** Minimal, crucial parameters (e.g., `job_id`, sanitized target path, operation type, specific processing flags) are passed from Python to the Rust core. Large data payloads are generally avoided at this boundary.

### 4. High-Performance Processing by Rust Core

*   **Component:** VēgaFS Rust Core (within `rust_core/src`).
*   **Action:**
    *   Receives the processing task and parameters from the Python orchestrator.
    *   Directly interacts with the **Primary Data Storage (File System / Object Storage)** to read, process, and potentially write files.
    *   Utilizes `Rayon` to parallelize data-intensive tasks across multiple CPU cores, such as recursively traversing large directory trees or applying operations to numerous files concurrently.
    *   Leverages `Tokio` for asynchronous I/O operations, ensuring non-blocking performance when reading or writing many files, crucial for high throughput.
    *   Performs the core computation as requested by the job (e.g., calculating sizes, content analysis, data transformation, thumbnail generation).
    *   May interact with **Redis** to store or retrieve frequently accessed metadata or intermediate processing results, acting as a read-through/write-through cache.
*   **Data Transmitted:** Reads/writes from/to Primary Storage; potentially writes to Redis; returns the final computation result (or a reference/summary of it) and status back to the Python orchestration layer.

### 5. Result Handling and Storage

*   **Component:** Python Orchestration Logic (within `app/core/processor.py`) and FastAPI Layer.
*   **Action:**
    *   Receives the result data (or a status/reference to large external results) from the Rust core.
    *   Updates the job status in **PostgreSQL** to `COMPLETED`, `FAILED`, or `CANCELLED` based on the outcome.
    *   Stores the final processing result, or a link/reference to where large results are stored (e.g., a path in object storage), within the corresponding job entry in **PostgreSQL**. The `JSONB` data type in PostgreSQL is used for flexible storage of unstructured result summaries.
    *   If applicable, the orchestrator might also push key results or summaries into **Redis** for rapid retrieval by the API layer, speeding up subsequent requests for the same job's output.
    *   The API layer can then serve these results to the client when a `GET /jobs/{job_id}` request is made.
*   **Data Transmitted:** Updated job status, final results, or references to results, stored in PostgreSQL and potentially cached in Redis.

## Integration Points

*   **External API (RESTful):** Built with FastAPI, this is the main entry point for all external interactions. It exposes endpoints for job management (`/jobs`), file system operations (`/fs`), and health checks.
*   **Internal API (PyO3 Language Bridge):** The critical high-performance communication channel between Python and Rust. This is a direct Foreign Function Interface (FFI) call, allowing Python to invoke Rust functions with minimal overhead, central to the system's performance.
*   **Database Interactions:** Python's SQLAlchemy ORM and `psycopg2` driver manage interactions with PostgreSQL for job metadata and results.
*   **Cache Interactions:** Python's Redis client is used by the orchestration layer to interact with Redis for caching purposes. While Rust can also interact with Redis, the primary caching logic for job results is handled by the Python orchestrator in the current design.
*   **File System / Object Storage Interactions:** The Rust core directly handles high-performance I/O operations with the underlying file system or object storage services (like AWS S3, GCP GCS, Azure Blob Storage), ensuring optimal data throughput during processing.

## Conceptual Data Flow Diagram

```text
+-------------------+      HTTP/CLI       +---------------------+
|      Client       |-------------------->|     API Layer       |
|  (Web UI / CLI)   |                     |     (FastAPI)       |
+-------------------+                     +----------+----------+
          ^                                          |
          |                                          | 2. Create Job (PostgreSQL)
          |                                          V
          |                               +----------+----------+
          |                               |   Orchestration     |
          |  5. Job Results/Status        |   Logic (Python)    |
          |  (from PostgreSQL/Redis)      +----------+----------+
          |                                          |
          |                                          | 3. In-process Call (PyO3)
          |                                          V
+---------+---------+  Reads/Writes Files  +----------+----------+
| Primary Data      |<-------------------->|   VēgaFS Rust Core  |
| Storage           |                      |  (Rayon, Tokio)     |
| (FS / S3 / GCS)   |                      +----------+----------+
+-------------------+                                  |
          ^                                          | 4. Caching (Redis)
          |                                          V
+---------+---------+                       +-------------------+
|  PostgreSQL       |<--------------------->|       Redis       |
| (Job Metadata,    | 5. Update Job Status  |      (Cache)      |
|  Results)         |                       +-------------------+
+-------------------+
```