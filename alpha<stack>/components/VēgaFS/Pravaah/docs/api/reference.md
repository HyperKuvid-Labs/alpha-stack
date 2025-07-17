# VēgaFS API Reference

This document provides a comprehensive reference for the VēgaFS RESTful API, detailing all available endpoints, their functionalities, expected parameters, and responses.

## Authentication

All API endpoints require authentication. API keys are expected to be sent in the `Authorization` header as a Bearer token:

`Authorization: Bearer YOUR_API_KEY`

Failure to provide a valid API key will result in a `401 Unauthorized` response.

---

## Health Check

### `GET /health`

Checks the health and availability of the API server. This endpoint can be used for liveness probes in container orchestration environments.

#### Request

`GET /health`

#### Query Parameters

None.

#### Request Body

None.

#### Responses

- **`200 OK`**
  Successful response indicating the service is operational.
  ```json
  {
    "status": "healthy"
  }
  ```

---

## Job Management

VēgaFS operates asynchronously for computationally intensive tasks. Jobs are submitted, their status can be monitored, and results retrieved once processing is complete.

### `POST /jobs`

Submits a new long-running file processing job to the VēgaFS engine.

#### Request

`POST /jobs`

#### Query Parameters

None.

#### Request Body

The request body defines the job to be executed. The `operation_type` determines the specific action to be performed by the VēgaFS Rust core.

```json
{
  "operation_type": "string",
  "path": "string",
  "parameters": {
    "key": "value"
  }
}
```

**Fields:**

- `operation_type` (string, **required**): Specifies the type of operation to perform.
  - Example values: `"summarize_directory"`, `"find_files"`, `"transform_files"`, `"bulk_move"`.
- `path` (string, **required**): The absolute path to the target file or directory on which the operation will be performed. Path inputs are sanitized to prevent path traversal vulnerabilities.
- `parameters` (object, optional): A dictionary of key-value pairs representing operation-specific arguments.
  - **For `summarize_directory`:**
    - `max_depth` (integer, optional): Maximum directory traversal depth.
    - `include_hidden` (boolean, optional): Whether to include hidden files/directories.
  - **For `find_files`:**
    - `pattern` (string, required): Regex or glob pattern for file names.
    - `min_size_bytes` (integer, optional): Minimum file size in bytes.
    - `max_size_bytes` (integer, optional): Maximum file size in bytes.
    - `modified_since` (ISO 8601 string, optional): Files modified after this timestamp.
  - **For `transform_files`:**
    - `source_file_type` (string, required): e.g., `"csv"`, `"jpeg"`.
    - `target_file_type` (string, required): e.g., `"parquet"`, `"webp"`.
    - `transformation_script` (string, optional): Base64 encoded script or path to a predefined transformation logic.
    - `output_directory` (string, optional): Directory to save transformed files.
  - *(Note: This list is illustrative and will expand as new operations are implemented.)*

#### Responses

- **`202 Accepted`**
  The job has been successfully submitted and is pending execution.
  ```json
  {
    "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "PENDING",
    "message": "Job submitted successfully"
  }
  ```
- **`400 Bad Request`**
  The request body is invalid or missing required fields.
  ```json
  {
    "detail": "Invalid job submission payload."
  }
  ```
- **`401 Unauthorized`**
  Authentication credentials were not provided or are invalid.
  ```json
  {
    "detail": "Not authenticated"
  }
  ```
- **`422 Unprocessable Entity`**
  Validation error for specific fields in the request body (e.g., path format, invalid parameters for operation_type).
  ```json
  {
    "detail": [
      {
        "loc": ["body", "path"],
        "msg": "value is not a valid absolute path",
        "type": "value_error"
      }
    ]
  }
  ```

### `GET /jobs/{job_id}`

Retrieves the current status and detailed results for a specific job.

#### Request

`GET /jobs/{job_id}`

#### Path Parameters

- `job_id` (string, **required**): The unique identifier of the job (UUID format).

#### Query Parameters

None.

#### Request Body

None.

#### Responses

- **`200 OK`**
  Returns the job status and, if completed, the results.
  ```json
  {
    "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "COMPLETED",
    "submitted_at": "2023-10-27T10:00:00Z",
    "started_at": "2023-10-27T10:00:05Z",
    "completed_at": "2023-10-27T10:01:30Z",
    "operation_type": "summarize_directory",
    "parameters": {
      "path": "/data/my-dataset",
      "max_depth": 2
    },
    "result": {
      "total_size_bytes": 51234567890,
      "file_count": 123456,
      "directory_count": 5678,
      "file_types": {
        "pdf": 1500,
        "csv": 2000,
        "txt": 5000,
        "jpg": 15000
      },
      "largest_files": [
        {"path": "/data/my-dataset/big_video.mp4", "size_bytes": 1000000000},
        {"path": "/data/my-dataset/archive.zip", "size_bytes": 500000000}
      ]
    }
  }
  ```
  **Possible `status` values:** `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.
  If `status` is `RUNNING`, a `progress` field (float from 0.0 to 1.0) might be included.
  If `status` is `FAILED`, an `error_message` field (string) and potentially an `error_details` object will be included.

- **`401 Unauthorized`**
  Authentication credentials were not provided or are invalid.
  ```json
  {
    "detail": "Not authenticated"
  }
  ```
- **`404 Not Found`**
  The specified `job_id` does not exist.
  ```json
  {
    "detail": "Job not found"
  }
  ```

---

## File System Operations

Direct file system queries for common operations that might not require a full job submission, typically for synchronous, quick insights.

### `GET /fs/summarize`

Calculates statistics for a given directory, including total size, file/folder count, and file type distribution. This operation is designed for quick insights and might have stricter limits on directory size/depth compared to a full `summarize_directory` job (which is submitted via `POST /jobs`).

#### Request

`GET /fs/summarize`

#### Query Parameters

- `path` (string, **required**): The absolute path to the directory to summarize. This path must be sanitized.
- `max_depth` (integer, optional): Maximum depth to traverse for the summary. Defaults to `1` (only immediate children of the specified path). For deeper or more extensive summaries, consider submitting a `summarize_directory` job.
- `include_hidden` (boolean, optional): Whether to include hidden files/directories in the summary. Defaults to `false`.

#### Request Body

None.

#### Responses

- **`200 OK`**
  Returns the summary statistics for the specified directory.
  ```json
  {
    "path": "/data/project-x",
    "total_size_bytes": 1234567890,
    "file_count": 10000,
    "directory_count": 500,
    "file_types": {
      "pdf": 150,
      "csv": 200,
      "json": 50,
      "md": 100
    },
    "last_modified": "2023-10-27T14:30:00Z"
  }
  ```
- **`400 Bad Request`**
  Invalid path or parameters provided (e.g., path is not absolute, `max_depth` is negative).
  ```json
  {
    "detail": "Invalid path or query parameters."
  }
  ```
- **`401 Unauthorized`**
  Authentication credentials were not provided or are invalid.
  ```json
  {
    "detail": "Not authenticated"
  }
  ```
- **`404 Not Found`**
  The specified path does not exist or is not a directory.
  ```json
  {
    "detail": "Path not found or is not a directory."
  }
  ```
- **`500 Internal Server Error`**
  An unexpected error occurred during summarization.
  ```json
  {
    "detail": "An error occurred during directory summarization. Please check server logs."
  }
  ```