# ADR 001: Python-Rust Hybrid Architecture for Project Sanchay

## Status

Accepted

## Context

Project Sanchay's core mission is to efficiently handle and process large collections of files and data. This involves CPU-bound tasks such as parallel directory traversal, file hashing, and metadata extraction, as well as providing a responsive, user-friendly graphical interface (GUI) and a flexible orchestration layer.

The development team is small (2-4 engineers) with a mandate for rapid time-to-market for an MVP, while also ensuring the system can scale to handle millions of files and maintain high performance. Traditional approaches of using a single language often present a trade-off: interpreted languages like Python offer rapid development and a rich ecosystem but can struggle with raw computational performance for CPU-intensive tasks, especially when constrained by the Global Interpreter Lock (GIL). Compiled languages like Rust offer unparalleled performance and memory safety but typically involve a steeper learning curve and slower development cycles for high-level application logic and GUI development.

Therefore, a decision is needed to select an architecture that balances these competing requirements, leveraging the strengths of different languages for distinct parts of the system.

## Decision

The project will adopt a hybrid architecture, combining Python for the user interface and high-level application orchestration with Rust for the performance-critical, CPU-bound core engine.

*   **Python (v3.10+)** will be used for:
    *   **User Interface:** Utilizing PySide6 for a native, cross-platform desktop GUI.
    *   **Application Logic/Orchestration:** Managing job queues, preparing data for the core engine, handling I/O-bound tasks (e.g., database interactions, network calls if applicable) with `asyncio`.
    *   **CLI:** Providing a command-line interface for headless operation.
    *   **External APIs (Optional):** Integrating with FastAPI for potential REST API exposure.

*   **Rust (v1.65+ - Stable)** will be used for:
    *   **High-Performance Core Engine:** Implementing all file/folder processing tasks.
    *   **Parallelism:** Leveraging Rayon for efficient data parallelism across multiple CPU cores.
    *   **Directory Traversal:** Using Walkdir for optimized filesystem scanning.
    *   **Core Algorithms:** Implementing file hashing, metadata extraction, and other computationally intensive logic.

*   **Python-Rust Integration:** PyO3 will be used to create seamless and efficient bindings, allowing Python code to call Rust functions directly with minimal overhead. Maturin will manage the build and packaging of the Rust core as a standard Python wheel.

## Consequences

### Positive Consequences

1.  **Optimal Performance:** Rust's native compilation and memory safety provide C-level performance for CPU-bound tasks, ensuring the application can scan and process millions of files efficiently and scale linearly with available CPU cores.
2.  **Responsive UI/Rapid Development:** Python with PySide6 enables quick development of a feature-rich, responsive GUI. Python's rich ecosystem (e.g., for database ORMs, configuration) accelerates the development of higher-level application logic.
3.  **Memory Safety and Concurrency:** Rust's compile-time guarantees prevent common memory-related bugs, enhancing the stability and security of the core engine. Its fearless concurrency model, combined with libraries like Rayon, allows for safe and efficient parallelism without GIL constraints.
4.  **Clear Separation of Concerns:** The architecture naturally enforces a clean separation between high-level orchestration/UI and low-level, performance-critical operations. This improves modularity, maintainability, and testability.
5.  **GIL Avoidance:** By offloading CPU-intensive work to Rust, the Python GIL is effectively bypassed for the most demanding computations, allowing the Python layer (and UI) to remain responsive.
6.  **Future Scalability:** The Rust core is well-positioned for future evolution into a standalone microservice if the application grows beyond a modular monolith, as it is already a distinct, compiled component.

### Negative Consequences

1.  **Increased Project Complexity:** Managing two distinct language toolchains (Python, Rust), build systems (pip, cargo, maturin), and dependency management introduces overhead.
2.  **Build and Distribution Challenges:** Creating cross-platform distributable binaries for Windows, macOS, and Linux becomes more complex due to the native Rust component, requiring careful CI/CD setup with platform-specific builds.
3.  **Learning Curve:** Developers need proficiency in both Python and Rust, including their respective ecosystems and the PyO3 binding layer. This can increase the onboarding time for new team members.
4.  **Integration Overhead:** While PyO3 minimizes the overhead, marshalling complex data structures between Python and Rust can introduce serialization/deserialization costs and require careful design of the interface.
5.  **Debugging Across Languages:** Debugging issues that span the Python-Rust boundary can be more challenging than debugging within a single language.
6.  **Potential for GIL Contention in Python Layer:** If the Python orchestration layer poorly manages calls to the Rust core or performs significant blocking I/O within the main thread, it can still lead to UI unresponsiveness, despite the Rust core being GIL-free. Proper use of `asyncio` and `QThread` (for PySide6) is crucial.

## Alternatives Considered

### 1. Pure Python (with C/Cython extensions where needed)

*   **Description:** Develop the entire application primarily in Python, potentially using C extensions (e.g., via Cython or `ctypes`) for performance-critical sections as an afterthought.
*   **Pros:** Simpler tooling initially, single language for most developers.
*   **Cons:**
    *   Python's GIL would severely limit true parallelism for CPU-bound tasks without explicit multiprocessing.
    *   Developing C extensions is often more cumbersome and error-prone (manual memory management) than using Rust for performance.
    *   Less memory-safe by default compared to Rust.
    *   Runtime performance for bulk file operations would likely be significantly lower than Rust.

### 2. Pure Rust with Web-based UI (e.g., Tauri)

*   **Description:** Build the entire application, including the UI, using Rust. For the GUI, a framework like Tauri (embedding a webview for HTML/CSS/JS UI) could be used, or a native Rust GUI library.
*   **Pros:** End-to-end Rust benefits (performance, memory safety, consistency), deep integration with the Rust ecosystem for all components.
*   **Cons:**
    *   Contradicts the explicit requirement for Python as the primary language for the UI and orchestration.
    *   Web-based UIs can have a larger memory footprint and may not feel as "native" as PySide6.
    *   Rust GUI libraries are less mature and involve a steeper learning curve for UI development compared to PySide6 for desktop applications.
    *   Requires different skillset for UI development (web technologies or specific Rust GUI frameworks).

### 3. C++/Python Hybrid

*   **Description:** Similar to the chosen Rust/Python approach, but using C++ for the high-performance core, integrated with Python via tools like `pybind11` or Cython.
*   **Pros:** High performance, mature ecosystem for C++.
*   **Cons:**
    *   C++ introduces significant memory safety risks and complexity compared to Rust.
    *   Steeper learning curve and higher potential for hard-to-debug crashes (segmentation faults, memory leaks).
    *   `pybind11` is excellent but the overall tooling for C++-Python integration might not be as streamlined as PyO3/Maturin for Rust, especially for cross-platform distribution.
    *   Does not offer the "fearless concurrency" benefits of Rust.

## Rationale for Decision

The chosen Python-Rust hybrid architecture offers the best balance of development velocity, performance, safety, and scalability for Project Sanchay. It allows us to leverage Python's strengths for rapid GUI and orchestration development while offloading critical, performance-intensive tasks to Rust, avoiding the Python GIL bottleneck and ensuring memory safety. The maturity of PyO3 and Maturin significantly mitigates the integration and distribution challenges inherent in a multi-language project. This approach directly addresses the core requirements for high performance, a responsive UI, and robust handling of large datasets, all within the constraints of a small development team and a tight schedule.