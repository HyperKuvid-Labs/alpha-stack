# Pravah User Guide

Welcome to the Pravah User Guide! This document provides practical, step-by-step instructions on how to set up, configure, and use Pravah for high-performance file and data processing.

Pravah is designed to efficiently scan, process, and transform large volumes of files across various storage systems, leveraging the power of Rust for core processing and Python for flexible orchestration and API interactions.

## 1. Getting Started

To get Pravah up and running on your local machine, follow these steps.

### Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Python 3.11+**: For the main application logic and API.
*   **Rust Toolchain**: Install via `rustup.rs`. This is required to build the `pravah_core` high-performance engine.
*   **Docker & Docker Compose**: For containerizing Pravah and its dependencies (like PostgreSQL) for local development.
*   **`make`**: A build automation tool used for simplified development commands.

### Local Development Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-org/pravah.git
    cd pravah
    ```

2.  **Configure Environment Variables**:
    Pravah uses environment variables for configuration. A template file `.env.example` is provided. Copy it to `.env` and fill in the necessary details.

    ```bash
    cp .env.example .env
    # Open .env with your text editor and customize
    ```

    At a minimum, configure the `DATABASE_URL` for your PostgreSQL instance. If using local Docker Compose, the default in `.env.example` should work.

    ```ini
    # .env example snippet
    DATABASE_URL=postgresql://user:password@db:5432/pravah_db
    # For S3/MinIO storage (optional)
    # AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
    # AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
    # S3_BUCKET_NAME=my-pravah-bucket
    # S3_ENDPOINT_URL=http://localhost:9000 # For MinIO
    ```

3.  **Start Docker Compose Services**:
    The `docker-compose.yml` file sets up the Pravah application, a PostgreSQL database, and optionally a MinIO server for local S3-compatible storage.

    ```bash
    make dev
    ```
    This command will:
    *   Build the `pravah_core` Rust library into a Python wheel using `maturin`.
    *   Build the Pravah Docker image.
    *   Start the `db` (PostgreSQL), `minio` (if enabled), and `app` containers.

    Alternatively, you can run `docker-compose up --build` directly.

4.  **Run Database Migrations**:
    Once the database container is running, apply the necessary schema migrations.

    ```bash
    make migrate
    ```

    The Pravah application should now be running and accessible.

## 2. Configuration

Pravah relies heavily on environment variables for configuration. During local development, these are loaded from the `.env` file. In production, it's recommended to use a secrets manager (e.g., AWS Secrets Manager, Kubernetes Secrets).

Key configuration parameters include:

*   **`LOG_LEVEL`**: (e.g., `INFO`, `DEBUG`, `WARNING`, `ERROR`) Controls the verbosity of application logs.
*   **`DATABASE_URL`**: The connection string for your PostgreSQL database (e.g., `postgresql://user:password@host:port/database`).
*   **`STORAGE_TYPE`**: (e.g., `local`, `s3`) Defines the default storage type for file operations.
*   **`S3_BUCKET_NAME`**: The name of the S3 bucket to use for cloud storage.
*   **`AWS_ACCESS_KEY_ID`**, **`AWS_SECRET_ACCESS_KEY`**: AWS credentials for S3 access.
*   **`S3_ENDPOINT_URL`**: Optional. Specify this if you are using a MinIO instance or another S3-compatible service (e.g., `http://localhost:9000`).

## 3. Using the Command Line Interface (CLI)

Pravah provides a powerful CLI built with Typer for various operations, especially useful for scripting and automation.

To execute a CLI command, you can use the `make cli` helper or run the Python module directly from within the Docker container or your local environment.

**General CLI Usage**:

```bash
# Using the make helper (recommended for local dev)
make cli -- <command> <subcommand> [options]

# Directly via python module (e.g., inside the Docker container or locally)
python app/cli.py <command> <subcommand> [options]
```

Replace `<command>`, `<subcommand>`, and `[options]` with the actual command you want to run. Use `--help` for more information on available commands and their arguments.

```bash
make cli -- --help
make cli -- jobs --help
```

### Example: Submitting a File Processing Job via CLI

Let's say you want to scan a local directory, process CSV files, and store the output in a MinIO bucket.

```bash
make cli -- jobs submit-scan \
    --source-path /app/data/input_files \
    --destination-path s3://pravah-output/processed_data \
    --processing-config-name extract_headers \
    --storage-type s3 \
    --recursive
```

**Explanation of parameters**:

*   `jobs submit-scan`: The command to submit a new file scanning and processing job.
*   `--source-path /app/data/input_files`: The source directory on the application's filesystem to scan. When running in Docker, this path corresponds to the path *inside* the container (e.g., a mounted volume).
*   `--destination-path s3://pravah-output/processed_data`: The target location for processed files. This example specifies an S3 path.
*   `--processing-config-name extract_headers`: The name of a predefined processing configuration to apply (e.g., `extract_headers` might extract the first line of CSVs).
*   `--storage-type s3`: Indicates that the destination is an S3-compatible storage. Use `local` for local filesystem.
*   `--recursive`: Processes files in subdirectories recursively.

Upon successful submission, the CLI will provide a `Job ID` that you can use to track the job's progress.

## 4. Using the REST API

Pravah exposes a RESTful API for programmatic interaction, ideal for integration with other applications or a web-based UI. The API is documented using OpenAPI (Swagger UI).

Once Pravah is running locally (e.g., via `make dev`), you can access the interactive API documentation at:
`http://localhost:8000/docs`

All API endpoints are prefixed with `/api/v1`.

### Example: Submitting a File Processing Job via API

To start a new processing job, send a `POST` request to the `/api/v1/jobs` endpoint.

**Endpoint**: `POST /api/v1/jobs`

**Request Body (JSON)**:

```json
{
    "source_path": "/data/input/my_large_dataset",
    "destination_path": "s3://my-pravah-bucket/processed_results",
    "processing_config_name": "compress_logs",
    "storage_type": "s3",
    "recursive": true
}
```

**Response (JSON)**:

```json
{
    "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "PENDING",
    "message": "Job submitted successfully."
}
```
*Note: The `source_path` and `destination_path` here refer to paths accessible by the Pravah application server.*

### Example: Checking Job Status

You can query the status of a submitted job using its `job_id`.

**Endpoint**: `GET /api/v1/jobs/{job_id}`

Replace `{job_id}` with the actual ID returned from the job submission.

**Example Request**: `GET http://localhost:8000/api/v1/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef`

**Response (JSON)**:

```json
{
    "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "RUNNING",
    "source_path": "/data/input/my_large_dataset",
    "destination_path": "s3://my-pravah-bucket/processed_results",
    "processing_config_name": "compress_logs",
    "storage_type": "s3",
    "recursive": true,
    "started_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T10:05:30Z",
    "progress": {
        "total_files": 15000,
        "processed_files": 5200,
        "errors": 10
    }
}
```

The `status` field will update from `PENDING` to `RUNNING`, `COMPLETED`, or `FAILED`. The `progress` object provides real-time updates on file counts during processing.

### Example: Retrieving Job Results

Once a job is `COMPLETED` or `FAILED`, you can fetch a summary of its results.

**Endpoint**: `GET /api/v1/jobs/{job_id}/results`

**Example Request**: `GET http://localhost:8000/api/v1/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef/results`

**Response (JSON)**:

```json
{
    "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "COMPLETED",
    "summary": {
        "total_files_scanned": 15000,
        "files_processed_successfully": 14990,
        "files_with_errors": 10,
        "processing_duration_seconds": 325.75,
        "output_location": "s3://my-pravah-bucket/processed_results"
    },
    "error_details": [
        {
            "file": "/data/input/my_large_dataset/corrupt_log_001.log",
            "message": "File format error: Invalid UTF-8 sequence",
            "timestamp": "2023-10-27T10:02:15Z"
        }
    ],
    "processed_files_list": [
        "s3://my-pravah-bucket/processed_results/log_001.gz",
        "s3://my-pravah-bucket/processed_results/log_002.gz",
        // ... (truncated for brevity)
    ]
}
```

The `summary` provides an overview, `error_details` lists specific issues, and `processed_files_list` gives the locations of successfully processed files.

### Viewing Available Processing Configurations

You can query the Pravah API to see the list of predefined processing configurations available.

**Endpoint**: `GET /api/v1/config`

**Example Request**: `GET http://localhost:8000/api/v1/config`

**Response (JSON)**:

```json
[
    {
        "name": "extract_headers",
        "description": "Extracts the header row from CSV files.",
        "input_formats": ["csv"],
        "output_format": "txt"
    },
    {
        "name": "compress_logs",
        "description": "Compresses log files into gzip format.",
        "input_formats": ["log"],
        "output_format": "gz"
    },
    {
        "name": "resize_images_1024",
        "description": "Resizes images to 1024x1024 pixels and converts to JPEG.",
        "input_formats": ["jpeg", "png"],
        "output_format": "jpeg"
    }
]
```

This endpoint helps you understand which `processing_config_name` values are valid for job submissions.

## 5. Understanding Job Results and Output

After a job completes, its `status` will be `COMPLETED` or `FAILED`. The output of the processing will be written to the `destination_path` specified in your job submission.

*   **For `local` storage**: Files will be saved to the specified path on the Pravah application's host filesystem (or within the Docker container's volume, if mounted).
*   **For `s3` storage**: Files will be uploaded to the specified S3 bucket and prefix.

The `GET /api/v1/jobs/{job_id}/results` endpoint provides a structured summary:

*   **`summary`**: High-level statistics like total files scanned, successfully processed, and duration.
*   **`error_details`**: A list of specific errors encountered during processing, including the file path and error message. This is crucial for debugging and identifying problematic files.
*   **`processed_files_list`**: A (potentially truncated) list of paths to the successfully processed output files. For very large jobs, this list might be limited or require further querying (e.g., listing the S3 bucket directly).

Always check the `status` and `error_details` to ensure your job executed as expected.

## 6. Advanced Topics

### Custom Processing Pipelines

While Pravah provides predefined processing configurations, the architecture is designed to allow for custom processing logic. In future releases, or for advanced users, there may be mechanisms to define or upload custom processing modules (e.g., Python scripts or Rust plugins) that can be executed by the core engine. Refer to the `architecture.md` documentation for more details on the core-plugin architecture.

### Monitoring

Pravah exposes Prometheus-compatible metrics at `http://localhost:8000/metrics`. These metrics provide insights into application performance, job counts, error rates, and processing durations, enabling robust monitoring and alerting for production deployments.

### Authentication

For production deployments, Pravah API endpoints are secured with JWT-based authentication. Refer to the API documentation (Swagger UI) for details on authentication flows and required headers (`Authorization: Bearer <token>`). User management and role-based access control (RBAC) are handled by the `auth` module.

---

Thank you for using Pravah! If you encounter any issues or have questions, please refer to the project's `README.md` or open an issue on the GitHub repository.