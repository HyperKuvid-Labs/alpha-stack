# Getting Started with Project Sanchay

Welcome to Project Sanchay! This guide will walk you through the process of installing, configuring, and running the application for the first time. Project Sanchay helps you efficiently manage and process large collections of files on your local system or cloud storage, leveraging the power of Rust for high-performance operations and Python for a user-friendly experience.

## 1. What is Project Sanchay?

Project Sanchay (meaning "collection" or "storage" in Hindi) is a powerful desktop application designed to help you organize, analyze, and process files. Whether you need to find duplicate images, generate metadata reports for millions of log files, or scan large directories for specific criteria, Sanchay provides a fast, reliable, and intuitive solution.

It features a modern graphical user interface (GUI) built with PySide6 and a high-performance core engine written in Rust, ensuring your file operations are lightning-fast and memory-safe.

## 2. Installation

Project Sanchay can be installed in two main ways: using a pre-built executable (recommended for most users) or by running it directly from the source code (for developers or advanced users).

### Option A: Using a Pre-built Executable (Recommended)

This is the easiest way to get started. Pre-built executables are self-contained and do not require you to install Python or Rust separately.

1.  **Download the Latest Release:**
    *   Visit the [Project Sanchay GitHub Releases page](https://github.com/your-organization/project-sanchay/releases) (replace `your-organization` with the actual GitHub organization or username).
    *   Download the appropriate executable for your operating system:
        *   **Windows (64-bit):** `sanchay-windows-x64.exe`
        *   **macOS (Intel):** `sanchay-macos-x64.dmg`
        *   **macOS (Apple Silicon):** `sanchay-macos-arm64.dmg`
        *   **Linux (64-bit):** `sanchay-linux-x64.AppImage` or `sanchay-linux-x64.deb`

2.  **Run the Application:**
    *   **Windows:** Double-click the `sanchay-windows-x64.exe` file.
    *   **macOS:**
        *   Open the downloaded `.dmg` file.
        *   Drag the "Project Sanchay" application icon into your Applications folder.
        *   Open "Project Sanchay" from your Applications folder. You might need to right-click and select "Open" the first time to bypass security warnings.
    *   **Linux:**
        *   **AppImage:** Make the AppImage executable (`chmod +x sanchay-linux-x64.AppImage`) and then run it (`./sanchay-linux-x64.AppImage`).
        *   **Debian/Ubuntu (.deb):** Install using `sudo dpkg -i sanchay-linux-x64.deb` and then launch from your applications menu or terminal (`sanchay`).

### Option B: Running from Source (For Developers)

If you wish to contribute to Project Sanchay, inspect the code, or require a specific development setup, you can run the application directly from its source code.

#### Prerequisites for Running from Source:

*   **Python 3.10+**: Ensure Python is installed and accessible via your system's PATH.
    *   [Download Python](https://www.python.org/downloads/)
*   **Rust Toolchain (v1.65+ Stable)**: Install Rust using `rustup`.
    *   Open your terminal and run: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
    *   Follow the on-screen instructions.
*   **Git**: For cloning the repository.

#### Steps:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-organization/project-sanchay.git
    cd project-sanchay
    ```

2.  **Set up a Python Virtual Environment:**
    It's highly recommended to use a virtual environment to manage dependencies.
    ```bash
    python -m venv .venv
    # On Windows:
    .\.venv\Scripts\activate
    # On macOS/Linux:
    source ./.venv/bin/activate
    ```

3.  **Install Maturin and Build Rust Core:**
    Maturin will compile the Rust core into a Python extension module and make it available to your virtual environment. Use `--release` for optimal performance.
    ```bash
    pip install maturin
    maturin develop --release
    ```
    *Note: `maturin develop` creates a symlink to the compiled Rust library. If you make changes to the Rust code, you'll need to re-run `maturin develop --release` to reflect those changes.*

4.  **Install Python Dependencies:**
    Install the Python application and its remaining dependencies. The `-e .` flag installs the project in "editable" mode, meaning changes to Python files will be immediately effective.
    ```bash
    pip install -e .
    ```

## 3. Configuration

Project Sanchay uses environment variables for configuration. For local settings, you can create a `.env` file in the root directory of the application (where `pyproject.toml` and `crates/` are located).

1.  **Create a `.env` file:**
    Copy the provided `.env.example` file and rename it to `.env` in the root `project-sanchay/` directory.
    ```bash
    # If using CLI:
    cp .env.example .env
    ```

2.  **Edit `.env`:**
    Open the newly created `.env` file in a text editor.
    ```ini
    # .env
    # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). INFO is recommended for general use.
    LOG_LEVEL=INFO

    # Path to the SQLite database file.
    # By default, Sanchay stores its database in a platform-specific application data directory:
    #   - Linux: ~/.local/share/sanchay/sanchay_metadata.db
    #   - macOS: ~/Library/Application Support/Sanchay/sanchay_metadata.db
    #   - Windows: %APPDATA%\Sanchay\sanchay_metadata.db
    # Uncomment and set this variable to a specific path if you want to override the default.
    # DATABASE_PATH=./my_custom_sanchay.db

    # AWS S3 / MinIO Configuration (Optional, for cloud storage integration)
    # Uncomment and fill these if you plan to process files from S3 or MinIO.
    # AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
    # AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
    # AWS_REGION=us-east-1
    # S3_ENDPOINT_URL= # Use this for MinIO or other S3-compatible services (e.g., http://localhost:9000)
    ```
    *   **`LOG_LEVEL`**: Controls the verbosity of log messages. `INFO` is generally suitable for daily use.
    *   **`DATABASE_PATH`**: If left commented, Sanchay will use a default location for its SQLite database. Uncomment and provide a path (e.g., `/path/to/my/data/sanchay.db`) if you want to control its location.
    *   **Cloud Storage**: If you plan to connect to AWS S3 or a MinIO instance, uncomment and fill in your credentials and region. Ensure these are stored securely.

## 4. First Run and Basic Usage (GUI)

Once installed and configured, you can launch Project Sanchay.

### Launching the GUI:

*   **Pre-built Executable:** Double-click the application icon or executable file.
*   **From Source:**
    ```bash
    # Ensure your virtual environment is active
    source ./.venv/bin/activate
    python -m src.sanchay_app
    ```

### Performing Your First Scan:

1.  **Welcome Screen:** The main Project Sanchay window will appear.
2.  **Select Directory:** Click the "Select Directory" button and choose a folder on your computer that you want to analyze.
3.  **Choose Task:** Select a processing task from the available options (e.g., "Find Duplicates", "Generate Metadata Report", "Count Files by Type").
4.  **Configure Task (Optional):** Depending on the task, you might see additional options (e.g., hashing algorithm for duplicates, specific metadata fields to extract).
5.  **Start Processing:** Click the "Start" or "Analyze" button.
6.  **Monitor Progress:** The application will display a real-time progress indicator (e.g., percentage complete, files processed per second). The UI is designed to remain responsive even during intensive backend processing.
7.  **View Results:** Once the job is completed, the results will be displayed in a clear, user-friendly format (e.g., a table, a summary chart).

## 5. Command-Line Interface (CLI) Usage (Headless Mode)

Project Sanchay provides a command-line interface for scripting and automation, allowing you to run tasks without launching the graphical user interface.

### Launching the CLI:

*   **Pre-built Executable:**
    *   **Windows:** Open Command Prompt or PowerShell, navigate to the executable's directory, and run `sanchay-windows-x64.exe --help`.
    *   **macOS/Linux:** Open your terminal and run `sanchay --help`. (You might need to ensure the executable's directory is in your system's PATH).
*   **From Source:**
    ```bash
    # Ensure your virtual environment is active
    source ./.venv/bin/activate
    python -m src.sanchay_app --help
    ```

### Common CLI Commands:

*   **`--help`**: Display general help message and available subcommands.
    ```bash
    sanchay --help
    # or
    python -m src.sanchay_app --help
    ```
*   **`scan-metadata <path>`**: Scans a directory and generates a metadata report.
    ```bash
    sanchay scan-metadata /path/to/my/documents --output-format json --output-file metadata_report.json
    ```
    *   `--output-format`: Specify output format (e.g., `json`, `csv`).
    *   `--output-file`: Specify a file to save the report to.
*   **`find-duplicates <path>`**: Scans a directory to find duplicate files based on content hashes.
    ```bash
    sanchay find-duplicates /path/to/my/photos --delete-mode dry-run
    ```
    *   `--delete-mode`: `dry-run` (show what would be deleted without actually deleting), `confirm` (actually delete detected duplicates). *Use `confirm` with extreme caution!*
*   **`list-jobs`**: Lists all past and ongoing processing jobs.
    ```bash
    sanchay list-jobs
    ```

*Refer to the CLI's `--help` output for each subcommand (`sanchay <subcommand> --help`) for the most up-to-date list of options and usage examples.*

## 6. Troubleshooting

*   **Application does not launch (Pre-built Executable):**
    *   **Windows:** Ensure your antivirus or firewall isn't blocking the application.
    *   **macOS:** If you get a "Developer cannot be verified" message, right-click the application icon, select "Open," and then click "Open" in the dialog box.
    *   **Linux:** Ensure the AppImage has execute permissions (`chmod +x`). If using a `.deb` package, check for installation errors and missing dependencies.
*   **"Module not found" error (Running from Source):**
    *   Ensure your Python virtual environment is active (`source ./.venv/bin/activate`).
    *   Verify you successfully ran `maturin develop --release` and `pip install -e .`.
*   **Performance is slower than expected:**
    *   If running from source, ensure the Rust core was built in release mode (`maturin develop --release`). Debug builds are significantly slower.
    *   Check your system resources (CPU, disk I/O). While Sanchay utilizes multi-core CPUs, heavy disk usage or a slow drive can still be a bottleneck.
*   **Reporting Bugs:** If you encounter any issues, please report them on the [Project Sanchay GitHub Issues page](https://github.com/your-organization/project-sanchay/issues) (replace `your-organization` with the actual GitHub organization or username). Provide detailed steps to reproduce, your operating system, and the application version.

---

We hope you enjoy using Project Sanchay!