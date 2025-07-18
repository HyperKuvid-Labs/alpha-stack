# 001. Hybrid Monolith with FFI

## Status
Accepted

## Date
2023-10-26

## Deciders
* Lead Architect
* Backend Team Lead
* Rust Core Engineer

## Context
The Karyaksham project aims to provide an efficient and capable platform for large dataset processing. Key functional requirements include handling large file uploads (up to 50 GB), executing configurable processing pipelines, and providing asynchronous job execution with real-time monitoring. Non-functional requirements emphasize high performance (e.g., 1 GB CSV processing in < 45 seconds), scalability (100+ concurrent jobs), and rapid time-to-market for an MVP.

The core challenge lies in reconciling the need for rapid development and a rich ecosystem for API and orchestration (typically Python's strengths) with the requirement for extreme performance in CPU-bound data transformations (where Python often struggles). A pure Python solution for the core processing would likely fail to meet performance targets, while a pure Rust solution for the entire backend would significantly increase development time and complexity for the API layer.

## Decision
The system will adopt a "Hybrid Monolith" architecture. The primary backend will be implemented in Python (FastAPI) for API exposure, job orchestration (Celery), and database interaction. The core, computationally intensive data processing engine will be developed in Rust and integrated with the Python application as a native Python module via PyO3 (Foreign Function Interface - FFI).

All heavy processing tasks will be offloaded from the API to asynchronous Celery workers, which will then invoke the Rust engine. File storage will be handled by object storage (e.g., S3), with data streamed directly between object storage and the Rust engine where possible.

## Consequences

### Positive
*   **High Performance for Core Processing:** By leveraging Rust, we achieve unparalleled speed and memory safety for the most demanding data transformation tasks, directly addressing the critical performance NFR. Rayon will enable parallel processing, fully utilizing multi-core CPUs.
*   **Rapid API Development & Rich Ecosystem:** Python with FastAPI provides a highly productive environment for building the API, user management, and job orchestration logic. Its vast ecosystem simplifies integrations with databases (PostgreSQL), message brokers (Redis), and object storage.
*   **Low-Latency Interoperability:** PyO3 provides an extremely efficient, in-process communication channel between Python and Rust. This avoids the latency and overhead associated with network calls (e.g., gRPC) that would be present in a microservices architecture, crucial for high-throughput data processing.
*   **Simplified Initial Deployment:** Starting as a "majestic monolith" (a single deployable unit for the backend, albeit with separate worker processes) reduces initial operational complexity compared to a full microservices approach. Docker Compose for local development is straightforward.
*   **Clear Scalability Path:** The asynchronous task processing pattern naturally decouples the API from workers, allowing independent scaling of both components in Kubernetes based on load.
*   **Optimized Resource Utilization:** The Rust engine directly manages memory without a garbage collector, leading to more predictable and efficient resource usage for compute-intensive tasks.

### Negative
*   **Increased Development Complexity (FFI Boundary):** Managing the interface between Python and Rust (especially data serialization/deserialization, error handling) adds a layer of complexity. This requires careful design and strict adherence to PyO3 best practices.
*   **Tighter Coupling than Microservices:** While flexible, this architecture is more tightly coupled than a pure microservices approach. Changes to the Rust API might require recompilation and redeployment of the Python component.
*   **Mixed Language Toolchain:** Developers need proficiency in both Python and Rust, and the CI/CD pipeline must handle both build processes (compiling Rust into a Python wheel). This might increase the learning curve for new team members.
*   **Potential Bottlenecks Outside Rust:** While Rust handles computation, overall performance can still be hampered by inefficient I/O in the Python layer (e.g., slow database queries, blocking network calls to object storage if not properly async).

### Mitigation & Follow-Up
*   **Standardized FFI Patterns:** Establish clear conventions for data types, error propagation, and function signatures at the Python-Rust boundary early in development. Conduct a dedicated "spike" to prototype complex data exchanges.
*   **Comprehensive Testing:** Implement robust unit, integration (especially Python-Rust), and end-to-end tests to catch issues related to the FFI boundary and overall system flow.
*   **Asynchronous Python I/O:** Mandate the use of asynchronous libraries (e.g., `aiobotocore` for S3, `asyncpg` for PostgreSQL) in the Python layer to prevent I/O from becoming a bottleneck.
*   **Distributed Tracing & Profiling:** Implement OpenTelemetry from day one to gain full visibility into the entire request lifecycle and identify performance bottlenecks across all components. Regularly profile the application under load.
*   **Continuous Integration/Deployment:** Automate the multi-stage Docker build process (Rust compilation + Python application) and deployment to ensure consistency and reliability across environments.
*   **Monitor and Re-evaluate:** Continuously monitor system performance and team velocity. If the "monolith" becomes unwieldy or the coupling becomes a significant constraint, revisit the architecture for potential component extraction into separate microservices (e.g., dedicated Rust service via gRPC).