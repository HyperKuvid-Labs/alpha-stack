# Project Sanchay

**High-Performance File and Data Collection Processing with Python and Rust**

Sanchay (सञ्चय), a Hindi word meaning "collection" or "storage," is a powerful cross-platform desktop application designed for efficient handling and processing of large collections of files and data. It leverages the expressiveness of Python for its user interface and orchestration layer, coupled with the unparalleled performance and memory safety of Rust for its core file processing engine.

## Table of Contents

1.  [About Project Sanchay](#about-project-sanchay)
2.  [Key Features](#key-features)
3.  [Technical Stack](#technical-stack)
4.  [Architecture Overview](#architecture-overview)
5.  [Getting Started](#getting-started)
    *   [Prerequisites](#prerequisites)
    *   [Cloning the Repository](#cloning-the-repository)
    *   [Setup and Installation](#setup-and-installation)
    *   [Configuration](#configuration)
    *   [Running the Application](#running-the-application)
6.  [Running Tests](#running-tests)
7.  [Contributing](#contributing)
8.  [License](#license)

## About Project Sanchay

In today's data-rich environments, managing vast numbers of files—from logs and media archives to scientific datasets—presents significant challenges. Project Sanchay addresses this by providing a robust and performant solution for tasks such as parallel directory scanning, checksum generation, metadata extraction, and duplicate file detection. By integrating a Rust-powered backend, Sanchay ensures that even petabyte-scale datasets can be processed efficiently, without compromising the responsiveness and user-friendliness of a modern desktop application.

## Key Features

*   **Directory Scanning:** Select local filesystem directories or specified cloud storage paths for processing.
*   **Parallel Processing:** Leverage multi-core CPUs for lightning-fast file operations like checksum generation, metadata extraction, and file counting.
*   **Real-time Job Management:** Monitor ongoing processing jobs with live progress indicators, including percentage complete and files processed per second.
*   **Results Visualization:** View processing results (e.g., duplicate files, file type summaries) in a clear, interactive user interface.
*   **Headless Operation (CLI):** Execute processing tasks via a command-line interface for scripting, automation, and integration into existing workflows.
*   **Cross-Platform:** Native support for Windows, macOS, and Linux.

## Technical Stack

Project Sanchay is built upon a hybrid technology stack carefully chosen for performance, safety, and developer productivity:

*   **Python 3.10+**: Primary language for the UI (PySide6) and application orchestration.
*   **Rust 1.65+**: Powers the high-performance, memory-safe core engine for all intensive file/folder processing tasks.
*   **PySide6**: Provides a professional, native-feeling, and cross-platform graphical user interface.
*   **PyO3 & Maturin**: Enables seamless and efficient communication between Python and Rust components.
*   **Rayon**: Rust library for effortless data parallelism in the core engine.
*   **Walkdir**: Optimized Rust library for efficient directory tree traversal.
*   **SQLite**: Serverless, self-contained database for local metadata storage.
*   **Docker**: For consistent and reproducible build/runtime environments.
*   **GitHub Actions**: CI/CD pipeline for automated testing, building, and deployment.

For detailed information on the technology choices, refer to the [Technical Stack Documentation](docs/technical_stack.md).

## Architecture Overview

Sanchay employs a **Modular Monolith with a Native Extension Core** architecture. This design principle ensures a streamlined development and deployment process while isolating performance-critical operations within the Rust core.

1.  **User Interface (PySide6)**: The GUI allows users to initiate and manage processing jobs.
2.  **Application Logic (Python)**: This layer orchestrates tasks, manages job queues, and prepares data for the Rust core. It uses `asyncio` for responsiveness.
3.  **Python-Rust Bridge (PyO3)**: Facilitates efficient data exchange and function calls between Python and the compiled Rust library.
4.  **Rust Core Engine (Rust)**: The stateless workhorse that performs parallel file operations (hashing, scanning) using `Rayon` and `walkdir`, operating without Python's Global Interpreter Lock (GIL).
5.  **Metadata Store (SQLite)**: Stores processing results, job statuses, and file metadata, accessible by both Python and Rust components.

**Data Flow Example (File Hashing & Metadata Extraction):**
A user selects a directory in the GUI. The Python application logic then calls a Rust function via PyO3, passing the directory path. The Rust core efficiently traverses the directory and processes files in parallel, calculating hashes and extracting metadata. The results are returned to Python, displayed in the UI, and persisted in the SQLite database.

For more architectural details, including optional external APIs, see [Architecture Overview](docs/architecture_overview.md).

## Getting Started

Follow these steps to set up and run Project Sanchay on your local machine.

### Prerequisites

Before you begin, ensure you have the following installed:

*   **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/).
*   **Rust Toolchain**: Install via `rustup` by running `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh` in your terminal.
*   **Git**: For cloning the repository.

### Cloning the Repository

First, clone the Project Sanchay repository to your local machine:

```bash
git clone https://github.com/your-org/project-sanchay.git
cd project-sanchay
```
*(Replace `https://github.com/your-org/project-sanchay.git` with the actual repository URL)*

### Setup and Installation

1.  **Create and Activate a Python Virtual Environment:**
    It's highly recommended to use a virtual environment to manage dependencies.

    ```bash
    python -m venv .venv
    # On macOS/Linux:
    source .venv/bin/activate
    # On Windows:
    .\.venv\Scripts\activate
    ```

2.  **Install Project Dependencies (including Rust core compilation):**
    The `pyproject.toml` file at the root of the project specifies `maturin` as the build backend for the Rust extension. Running `pip install -e .` will automatically build the `sanchay_core` Rust library and install all Python dependencies.

    ```bash
    # Ensure maturin is available for the build process (might be implicitly handled by pip, but good practice)
    pip install maturin

    # Install Python dependencies and build the Rust core (sanchay_core)
    # The `-e` flag installs in "editable" mode, useful for development.
    pip install -e .
    ```

### Configuration

Project Sanchay uses environment variables for configuration. An example file `config/.env.example` is provided.

1.  **Create a `.env` file:**
    Copy the example environment file to the project root and rename it to `.env`.

    ```bash
    cp config/.env.example .env
    ```

2.  **Edit `.env` (Optional):**
    Open the `.env` file and adjust settings like `LOG_LEVEL` or `DATABASE_PATH` as needed.
    ```ini
    # .env
    LOG_LEVEL=INFO
    DATABASE_PATH=./sanchay_metadata.db
    # Add other environment variables as per config/.env.example
    ```
    This file is ignored by Git and intended for local development.

### Running the Application

Once installed, you can run Sanchay in either GUI or CLI mode.

*   **GUI Mode:**
    Launch the graphical user interface.

    ```bash
    python -m src.sanchay_app
    ```

*   **CLI Mode (Headless Operation):**
    Run Sanchay from the command line for scripting or automation. Use `--help` to see available commands and options.

    ```bash
    python -m src.sanchay_app --help
    # Example: Scan a directory and output metadata to a JSON file
    # python -m src.sanchay_app scan --path /data/my_files --output-json ./scan_results.json
    ```

For a more detailed user guide, refer to [docs/user_guide/getting_started.md](docs/user_guide/getting_started.md).

## Running Tests

Project Sanchay includes comprehensive unit and integration tests for both its Python and Rust components.

1.  **Activate your virtual environment (if not already active):**
    ```bash
    source .venv/bin/activate
    ```

2.  **Run Rust Tests:**
    Navigate to the Rust crate directory and run `cargo test`.

    ```bash
    cd crates/sanchay_core
    cargo test
    cd ../.. # Return to project root
    ```

3.  **Run Python Tests:**
    From the project root, use `pytest` to run all Python tests.

    ```bash
    pytest tests/
    # To run specific test suites, e.g., integration tests:
    # pytest tests/integration/
    ```

## Contributing

We welcome contributions to Project Sanchay! If you're interested in improving the application, please refer to our [CONTRIBUTING.md](CONTRIBUTING.md) guide (forthcoming) for details on how to set up your development environment, propose changes, and submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.