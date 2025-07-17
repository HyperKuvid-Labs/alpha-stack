# Pravah: High-Performance File & Data Processing Engine - Architecture Overview

This document outlines the high-level system architecture of Pravah, detailing its major components, their interactions, data flows, and key design decisions. It serves as a guide for developers to understand how the system is constructed.

## System Design Pattern

**Modular Monolith with a Core-Plugin Architecture:** The system is designed as a single deployable unit (a monolith) for simplicity in initial development and deployment. However, it's internally structured with high modularity. The high-performance Rust engine acts as a "core plugin" to the main Python application. This architecture allows the performance-critical component (Rust) to be developed and optimized independently of the application logic (Python), offering a clear separation of concerns and a straightforward path to potentially extracting it into a separate microservice in the future if needed.

## Components & Data Flow

1.  **User Interface (CLI / Web UI):** The user initiates a job, e.g., "Process all `.csv` files in directory X."

2.  **API Layer (FastAPI):** The request is received by the FastAPI backend. It validates the input parameters (e.g., file path, processing options) using Pydantic models.

3.  **Job Orchestrator (Python Logic):** A new job is created and its initial state (`PENDING`) is persisted in the PostgreSQL database. The job details are passed to the core processing logic.

4.  **Python-Rust Bridge (PyO3):** The Python orchestrator calls the main processing function in the compiled Rust library, passing the job parameters (e.g., directory path, configuration).

5.  **Rust Core Engine (`pravah_core`):**
    *   Uses `walkdir` and `tokio` to asynchronously and concurrently scan the target directory for files.
    *   For each file, it spawns a task. For CPU-bound processing on the file's content, it uses a `rayon` thread pool to parallelize the work across all available CPU cores.
    *   Progress and results are communicated back to the Python layer, either through callbacks or by returning a final summary.

6.  **Data Persistence:** The results are written to the specified destination (filesystem or S3), and the job status in PostgreSQL is updated to `COMPLETED` or `FAILED`.

7.  **Feedback to User:** The API layer returns a job ID to the user, who can then poll an endpoint to check the status and retrieve the results.

## Integration & APIs

*   **Internal API (Python <> Rust):** A tightly-coupled, in-process API defined using `PyO3`. Data structures are shared using types that can be seamlessly converted between Python objects and Rust structs. This is optimized for performance, minimizing serialization overhead.

*   **External API (REST):** A public-facing REST API exposed via FastAPI. This will be the primary way for users and other services to interact with Pravah. It will follow OpenAPI standards and include endpoints for:
    *   `POST /jobs`: Create and start a new processing job.
    *   `GET /jobs/{job_id}`: Check the status and progress of a job.
    *   `GET /jobs/{job_id}/results`: Retrieve the results of a completed job.
    *   `GET /config`: View available processing configurations.