# Karyaksham Backend API Documentation

This document provides a comprehensive guide to interacting with the Karyaksham backend API. The API is RESTful, designed for efficiency, and secured using JSON Web Tokens (JWT).

## 1. Base URL

All API requests should be prefixed with the base URL and version:

`https://[YOUR_API_DOMAIN]/api/v1`

For local development, this might be `http://localhost:8000/api/v1`.

## 2. Authentication

Karyaksham API uses JWT for authentication.

### 2.1. Obtaining an Access Token

First, you need to register and/or log in to obtain an `access_token`.

#### Endpoint: `POST /auth/register`

Registers a new user account.

-   **Description**: Creates a new user with the provided email and password.
-   **Method**: `POST`
-   **URL**: `/auth/register`
-   **Request Body (JSON)**:
    ```json
    {
      "email": "user@example.com",
      "password": "securepassword123"
    }
    ```
-   **Response (JSON)**:
    ```json
    {
      "id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
      "email": "user@example.com"
    }
    ```
-   **Status Codes**:
    -   `201 Created`: User successfully registered.
    -   `400 Bad Request`: Invalid input or email already registered.

#### Endpoint: `POST /auth/login`

Authenticates a user and issues an access token.

-   **Description**: Logs in an existing user and provides a JWT `access_token`.
-   **Method**: `POST`
-   **URL**: `/auth/login`
-   **Request Body (x-www-form-urlencoded)**:
    ```
    username=user@example.com&password=securepassword123
    ```
    (Note: This endpoint expects `username` for the email, as per OAuth2 standard for password flow.)
-   **Response (JSON)**:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer"
    }
    ```
-   **Status Codes**:
    -   `200 OK`: Authentication successful.
    -   `400 Bad Request`: Invalid credentials.

### 2.2. Using the Access Token

Once you have an `access_token`, include it in the `Authorization` header of all subsequent protected requests.

-   **Header**: `Authorization`
-   **Value**: `Bearer <YOUR_ACCESS_TOKEN>`

**Example**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 3. Common Data Types and Schemas

The API uses Pydantic schemas for request and response validation. For full details on schema definitions, refer to the source code located in `backend/src/karyaksham_api/schemas/`.

-   `UserCreate`, `UserResponse`: For user registration and details.
-   `Token`: For authentication tokens.
-   `JobCreate`, `JobResponse`: For creating and retrieving job information.
-   `ProcessingStep`: A sub-schema within `JobCreate` defining transformation steps.

## 4. Error Handling

The API returns standard HTTP status codes and JSON-formatted error responses for failures.

**Example Error Response**:
```json
{
  "detail": "Unauthorized: Invalid authentication credentials"
}
```

Common status codes:
-   `2xx`: Success
-   `400 Bad Request`: General client-side error (e.g., malformed request body, validation error).
-   `401 Unauthorized`: Authentication required or invalid token.
-   `403 Forbidden`: Authenticated but not authorized to access the resource.
-   `404 Not Found`: Resource not found.
-   `422 Unprocessable Entity`: Validation error due to invalid input data.
-   `500 Internal Server Error`: Server-side error.

## 5. API Endpoints

### 5.1. User Endpoints

#### Endpoint: `GET /users/me`

Retrieves the details of the currently authenticated user.

-   **Description**: Returns the email and ID of the user associated with the provided JWT.
-   **Method**: `GET`
-   **URL**: `/users/me`
-   **Authentication**: Required.
-   **Response (JSON)**:
    ```json
    {
      "id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
      "email": "user@example.com"
    }
    ```
-   **Status Codes**:
    -   `200 OK`: User details retrieved successfully.
    -   `401 Unauthorized`: Invalid or missing token.

### 5.2. Job Management Endpoints

#### Endpoint: `POST /jobs`

Initiates a new file processing job.

-   **Description**: Creates a new job entry in the database. This does *not* upload the file. It provides the job metadata and prepares for file upload.
-   **Method**: `POST`
-   **URL**: `/jobs`
-   **Authentication**: Required.
-   **Request Body (JSON)**:
    ```json
    {
      "file_name": "my_large_data.csv",
      "original_file_size_bytes": 1024000000,
      "processing_steps": [
        {
          "type": "filter",
          "params": {
            "column": "country",
            "operator": "eq",
            "value": "India"
          }
        },
        {
          "type": "convert_format",
          "params": {
            "to_format": "parquet"
          }
        }
      ]
    }
    ```
-   **Response (JSON)**:
    ```json
    {
      "id": "d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f",
      "user_id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
      "file_name": "my_large_data.csv",
      "original_file_size_bytes": 1024000000,
      "status": "PENDING",
      "processing_steps": [
        {
          "type": "filter",
          "params": {
            "column": "country",
            "operator": "eq",
            "value": "India"
          }
        },
        {
          "type": "convert_format",
          "params": {
            "to_format": "parquet"
          }
        }
      ],
      "created_at": "2023-10-27T10:00:00.000Z",
      "updated_at": "2023-10-27T10:00:00.000Z",
      "input_object_key": null,
      "output_object_key": null,
      "error_message": null
    }
    ```
-   **Status Codes**:
    -   `201 Created`: Job initiated successfully.
    -   `400 Bad Request`: Invalid input (e.g., missing `file_name`, malformed `processing_steps`).

#### Endpoint: `GET /jobs`

Retrieves a list of processing jobs for the authenticated user.

-   **Description**: Lists all jobs created by the current user. Supports pagination.
-   **Method**: `GET`
-   **URL**: `/jobs`
-   **Authentication**: Required.
-   **Query Parameters**:
    -   `skip` (integer, optional): Number of items to skip (for pagination). Default: `0`.
    -   `limit` (integer, optional): Maximum number of items to return. Default: `100`.
-   **Response (JSON)**:
    ```json
    [
      {
        "id": "d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f",
        "user_id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
        "file_name": "my_large_data.csv",
        "original_file_size_bytes": 1024000000,
        "status": "PENDING",
        "processing_steps": [],
        "created_at": "2023-10-27T10:00:00.000Z",
        "updated_at": "2023-10-27T10:00:00.000Z",
        "input_object_key": null,
        "output_object_key": null,
        "error_message": null
      },
      {
        "id": "e3f9g2d8-b5c6-5d7e-0f1g-2b3c4d5e6f7g",
        "user_id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
        "file_name": "another_file.json",
        "original_file_size_bytes": 50000000,
        "status": "COMPLETED",
        "processing_steps": [],
        "created_at": "2023-10-26T09:30:00.000Z",
        "updated_at": "2023-10-26T10:15:00.000Z",
        "input_object_key": "karyaksham-data/user-c1f7a2b9/another_file.json",
        "output_object_key": "karyaksham-data/user-c1f7a2b9/processed/another_file_out.json",
        "error_message": null
      }
    ]
    ```
-   **Status Codes**:
    -   `200 OK`: List of jobs retrieved successfully.
    -   `401 Unauthorized`: Invalid or missing token.

#### Endpoint: `GET /jobs/{job_id}`

Retrieves details for a specific job.

-   **Description**: Fetches the full details of a job by its unique ID.
-   **Method**: `GET`
-   **URL**: `/jobs/{job_id}` (e.g., `/jobs/d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f`)
-   **Authentication**: Required.
-   **Response (JSON)**: (Same as individual `JobResponse` from `POST /jobs` or an item from `GET /jobs`)
    ```json
    {
      "id": "d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f",
      "user_id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
      "file_name": "my_large_data.csv",
      "original_file_size_bytes": 1024000000,
      "status": "PENDING",
      "processing_steps": [],
      "created_at": "2023-10-27T10:00:00.000Z",
      "updated_at": "2023-10-27T10:00:00.000Z",
      "input_object_key": null,
      "output_object_key": null,
      "error_message": null
    }
    ```
-   **Status Codes**:
    -   `200 OK`: Job details retrieved.
    -   `401 Unauthorized`: Invalid or missing token.
    -   `403 Forbidden`: User does not own this job.
    -   `404 Not Found`: Job ID not found.

#### Endpoint: `POST /jobs/{job_id}/upload-url`

Generates a presigned URL for direct file upload to object storage.

-   **Description**: After initiating a job, call this endpoint to get a temporary URL that allows the client to directly upload the input file to the configured object storage (e.g., S3, MinIO).
-   **Method**: `POST`
-   **URL**: `/jobs/{job_id}/upload-url`
-   **Authentication**: Required.
-   **Request Body (JSON)**: Empty `{}`.
-   **Response (JSON)**:
    ```json
    {
      "upload_url": "https://minio.yourdomain.com/karyaksham-data/input/d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f/my_large_data.csv?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
    }
    ```
-   **Status Codes**:
    -   `200 OK`: Presigned URL generated.
    -   `400 Bad Request`: Job not in `PENDING` state, or already has an upload URL.
    -   `401 Unauthorized`: Invalid or missing token.
    -   `403 Forbidden`: User does not own this job.
    -   `404 Not Found`: Job ID not found.

#### Endpoint: `POST /jobs/{job_id}/mark-uploaded`

Notifies the API that the input file for a job has been successfully uploaded.

-   **Description**: After the client has uploaded the file using the presigned URL, this endpoint *must* be called to confirm the upload. This triggers the actual processing task in the background.
-   **Method**: `POST`
-   **URL**: `/jobs/{job_id}/mark-uploaded`
-   **Authentication**: Required.
-   **Request Body (JSON)**:
    ```json
    {
      "object_key": "input/d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f/my_large_data.csv"
    }
    ```
    (This `object_key` is typically part of the `upload_url` generated previously, after the bucket name.)
-   **Response (JSON)**: (Updated `JobResponse` object)
    ```json
    {
      "id": "d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f",
      "user_id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
      "file_name": "my_large_data.csv",
      "original_file_size_bytes": 1024000000,
      "status": "QUEUED",
      "processing_steps": [],
      "created_at": "2023-10-27T10:00:00.000Z",
      "updated_at": "2023-10-27T10:05:00.000Z",
      "input_object_key": "input/d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f/my_large_data.csv",
      "output_object_key": null,
      "error_message": null
    }
    ```
-   **Status Codes**:
    -   `200 OK`: Job status updated to `QUEUED`, processing task dispatched.
    -   `400 Bad Request`: Job not in `PENDING` state, or `object_key` invalid.
    -   `401 Unauthorized`: Invalid or missing token.
    -   `403 Forbidden`: User does not own this job.
    -   `404 Not Found`: Job ID not found.

#### Endpoint: `POST /jobs/{job_id}/download-url`

Generates a presigned URL for downloading the processed output file.

-   **Description**: This endpoint provides a temporary URL to download the processed file. Only available when the job `status` is `COMPLETED`.
-   **Method**: `POST`
-   **URL**: `/jobs/{job_id}/download-url`
-   **Authentication**: Required.
-   **Request Body (JSON)**: Empty `{}`.
-   **Response (JSON)**:
    ```json
    {
      "download_url": "https://minio.yourdomain.com/karyaksham-data/output/d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f/my_large_data_processed.parquet?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
    }
    ```
-   **Status Codes**:
    -   `200 OK`: Presigned URL generated.
    -   `400 Bad Request`: Job not in `COMPLETED` state, or no output file available.
    -   `401 Unauthorized`: Invalid or missing token.
    -   `403 Forbidden`: User does not own this job.
    -   `404 Not Found`: Job ID not found.

#### Endpoint: `POST /jobs/{job_id}/cancel`

Requests cancellation of a running or queued job.

-   **Description**: Attempts to cancel a job. The actual cancellation might be asynchronous. The job status will change to `CANCELLATION_REQUESTED` or `CANCELLED`.
-   **Method**: `POST`
-   **URL**: `/jobs/{job_id}/cancel`
-   **Authentication**: Required.
-   **Request Body (JSON)**: Empty `{}`.
-   **Response (JSON)**: (Updated `JobResponse` object with `status` as `CANCELLATION_REQUESTED` or `CANCELLED`)
    ```json
    {
      "id": "d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f",
      "user_id": "c1f7a2b9-e3d4-4f5c-8a1b-0e9d8f7c6b5a",
      "file_name": "my_large_data.csv",
      "original_file_size_bytes": 1024000000,
      "status": "CANCELLATION_REQUESTED",
      "processing_steps": [],
      "created_at": "2023-10-27T10:00:00.000Z",
      "updated_at": "2023-10-27T10:10:00.000Z",
      "input_object_key": "input/d2e8f1c7-a4b5-4c6d-9e0f-1a2b3c4d5e6f/my_large_data.csv",
      "output_object_key": null,
      "error_message": null
    }
    ```
-   **Status Codes**:
    -   `200 OK`: Cancellation requested.
    -   `400 Bad Request`: Job not in a cancellable state.
    -   `401 Unauthorized`: Invalid or missing token.
    -   `403 Forbidden`: User does not own this job.
    -   `404 Not Found`: Job ID not found.

## 6. Example Workflow (cURL)

This section demonstrates a typical user flow for uploading and processing a file using cURL.

**Assumptions**:
-   API is running at `http://localhost:8000`.
-   MinIO is running and configured locally, accessible for direct file uploads.

### Step 1: Register a new user

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "devuser@example.com",
           "password": "devpassword"
         }'
# Expected output: {"id": "UUID", "email": "devuser@example.com"}
```

### Step 2: Login and get an Access Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=devuser@example.com&password=devpassword"
# Expected output: {"access_token": "YOUR_JWT_TOKEN", "token_type": "bearer"}
# Store YOUR_JWT_TOKEN for subsequent requests.
```

Let's assume `YOUR_JWT_TOKEN` is `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXZ1c2VyQGV4YW1wbGUuY29tIiwiZXhwIjoxNjk4NDU4MDAwfQ.signature`

### Step 3: Create a new processing job

```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "file_name": "sample_data.csv",
           "original_file_size_bytes": 10240,
           "processing_steps": [
             {"type": "filter", "params": {"column": "city", "operator": "eq", "value": "New York"}}
           ]
         }'
# Expected output: {"id": "JOB_UUID", "status": "PENDING", ...}
# Store JOB_UUID for the next steps.
```

Let's assume `JOB_UUID` is `abcde123-f456-7890-1234-abcdefghijkl`

### Step 4: Get a presigned upload URL for the input file

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/abcde123-f456-7890-1234-abcdefghijkl/upload-url" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{}'
# Expected output: {"upload_url": "https://minio:9000/karyaksham-data/input/abcde123-f456-7890-1234-abcdefghijkl/sample_data.csv?X-Amz-Algorithm=..."}
# Store the `upload_url`.
```

### Step 5: Upload the file directly to object storage (e.g., MinIO)

**Note**: This step bypasses the API server and uploads directly to your configured object storage. You'll need a sample `sample_data.csv` file.

```bash
# Example content for sample_data.csv:
# name,city,age
# Alice,New York,30
# Bob,London,25
# Charlie,New York,35

curl -X PUT "https://minio:9000/karyaksham-data/input/abcde123-f456-7890-1234-abcdefghijkl/sample_data.csv?X-Amz-Algorithm=..." \
     -H "Content-Type: text/csv" \
     --data-binary "@sample_data.csv"
# Expected output: (200 OK from MinIO, usually empty response body for PUT)
```

### Step 6: Mark the job's input file as uploaded

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/abcde123-f456-7890-1234-abcdefghijkl/mark-uploaded" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "object_key": "input/abcde123-f456-7890-1234-abcdefghijkl/sample_data.csv"
         }'
# Expected output: {"id": "abcde123-f456-7890-1234-abcdefghijkl", "status": "QUEUED", ...}
```

### Step 7: Poll job status (repeatedly)

You would typically poll this endpoint from the UI to show progress.

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/abcde123-f456-7890-1234-abcdefghijkl" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
# Expected output: {"id": "...", "status": "RUNNING"} then {"id": "...", "status": "COMPLETED", "output_object_key": "output/..."}
# If status becomes COMPLETED, note the output_object_key.
```

### Step 8: Get a presigned download URL for the output file (once completed)

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/abcde123-f456-7890-1234-abcdefghijkl/download-url" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{}'
# Expected output: {"download_url": "https://minio:9000/karyaksham-data/output/abcde123-f456-7890-1234-abcdefghijkl/sample_data_processed.csv?X-Amz-Algorithm=..."}
# Store the `download_url`.
```

### Step 9: Download the processed file

**Note**: This step downloads directly from your configured object storage.

```bash
curl -X GET "https://minio:9000/karyaksham-data/output/abcde123-f456-7890-1234-abcdefghijkl/sample_data_processed.csv?X-Amz-Algorithm=..." \
     -o processed_data.csv
# Expected output: Downloads the processed_data.csv file.
```