import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

# Assuming these imports exist based on the project structure
from app.db.models.job import Job
from app.api.v1.schemas import JobCreate, JobStatus, JobResult  # Assuming these Pydantic schemas exist


# Fixtures `app_client` and `db_session` are expected to be defined in tests/conftest.py
# app_client: An httpx.AsyncClient instance configured to make requests against the FastAPI app
# db_session: An SQLAlchemy session connected to an isolated test database


@pytest.mark.asyncio
async def test_health_check(app_client: AsyncClient):
    """
    Test the /health endpoint to ensure the API is running.
    """
    response = await app_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_job_success(app_client: AsyncClient, db_session: Session):
    """
    Test POST /jobs endpoint for successful job creation.
    Verifies API response and database persistence.
    """
    job_payload = {
        "source_path": "s3://my-bucket/input/data/",
        "destination_path": "file:///tmp/pravah_output/",
        "processing_options": {"format_conversion": "parquet", "compression_level": 9}
    }
    response = await app_client.post("/api/v1/jobs", json=job_payload)

    assert response.status_code == 201
    response_data = response.json()

    # Validate against expected schema
    # Use Pydantic schema for robust validation
    job_status_response = JobStatus(**response_data)

    assert job_status_response.status == "PENDING"
    assert job_status_response.source_path == job_payload["source_path"]
    assert job_status_response.destination_path == job_payload["destination_path"]
    assert job_status_response.processing_options == job_payload["processing_options"]
    assert isinstance(job_status_response.job_id, uuid.UUID)

    # Verify job persistence in the database
    db_job = db_session.query(Job).filter(Job.id == job_status_response.job_id).first()
    assert db_job is not None
    assert db_job.status == "PENDING"
    assert db_job.source_path == job_payload["source_path"]
    assert db_job.destination_path == job_payload["destination_path"]
    assert db_job.processing_options == job_payload["processing_options"]


@pytest.mark.asyncio
async def test_create_job_invalid_input(app_client: AsyncClient):
    """
    Test POST /jobs with invalid or missing required fields.
    """
    # Missing 'destination_path' which is required by JobCreate schema
    invalid_job_payload = {
        "source_path": "s3://invalid-path",
        "processing_options": {"mode": "fast"}
    }
    response = await app_client.post("/api/v1/jobs", json=invalid_job_payload)

    assert response.status_code == 422  # Unprocessable Entity
    assert "detail" in response.json()
    # Check that the error message indicates missing 'destination_path'
    assert any("destination_path" in err["loc"] for err in response.json()["detail"])


@pytest.mark.asyncio
async def test_get_job_status_exists(app_client: AsyncClient, db_session: Session):
    """
    Test GET /jobs/{job_id} for an existing job.
    """
    # Create a job directly in the database for a known state
    test_job_id = uuid.uuid4()
    new_job = Job(
        id=test_job_id,
        source_path="/local/path/to/files",
        destination_path="/local/path/to/results",
        status="RUNNING",
        processing_options={"extract_metadata": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(new_job)
    db_session.commit()
    db_session.refresh(new_job)

    response = await app_client.get(f"/api/v1/jobs/{new_job.id}")
    assert response.status_code == 200

    response_data = response.json()
    job_status_response = JobStatus(**response_data)

    assert job_status_response.job_id == new_job.id
    assert job_status_response.status == "RUNNING"
    assert job_status_response.source_path == new_job.source_path
    assert job_status_response.processing_options == new_job.processing_options


@pytest.mark.asyncio
async def test_get_job_status_not_found(app_client: AsyncClient):
    """
    Test GET /jobs/{job_id} for a non-existent job ID.
    """
    non_existent_job_id = uuid.uuid4()
    response = await app_client.get(f"/api/v1/jobs/{non_existent_job_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_get_job_results_completed(app_client: AsyncClient, db_session: Session):
    """
    Test GET /jobs/{job_id}/results for a successfully completed job.
    """
    test_job_id = uuid.uuid4()
    completed_job = Job(
        id=test_job_id,
        source_path="s3://source/path",
        destination_path="s3://dest/path",
        status="COMPLETED",
        processing_options={"resize": "1024x768"},
        result_details={"processed_files_count": 150, "errors": 0, "output_size_bytes": 1024000},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(completed_job)
    db_session.commit()
    db_session.refresh(completed_job)

    response = await app_client.get(f"/api/v1/jobs/{completed_job.id}/results")
    assert response.status_code == 200

    response_data = response.json()
    job_result_response = JobResult(**response_data)

    assert job_result_response.job_id == completed_job.id
    assert job_result_response.status == "COMPLETED"
    assert job_result_response.result_details == completed_job.result_details


@pytest.mark.asyncio
async def test_get_job_results_failed(app_client: AsyncClient, db_session: Session):
    """
    Test GET /jobs/{job_id}/results for a failed job.
    """
    test_job_id = uuid.uuid4()
    failed_job = Job(
        id=test_job_id,
        source_path="s3://source/path/broken",
        destination_path="s3://dest/path/failed",
        status="FAILED",
        processing_options={"extract_text": True},
        result_details={"error_message": "File not found", "failed_file": "doc1.pdf"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(failed_job)
    db_session.commit()
    db_session.refresh(failed_job)

    response = await app_client.get(f"/api/v1/jobs/{failed_job.id}/results")
    assert response.status_code == 200

    response_data = response.json()
    job_result_response = JobResult(**response_data)

    assert job_result_response.job_id == failed_job.id
    assert job_result_response.status == "FAILED"
    assert job_result_response.result_details == failed_job.result_details


@pytest.mark.asyncio
async def test_get_job_results_not_in_final_state(app_client: AsyncClient, db_session: Session):
    """
    Test GET /jobs/{job_id}/results for a job that is still PENDING or RUNNING.
    """
    test_job_id = uuid.uuid4()
    running_job = Job(
        id=test_job_id,
        source_path="s3://source/ongoing",
        destination_path="s3://dest/ongoing",
        status="RUNNING",  # Not COMPLETED or FAILED
        processing_options={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(running_job)
    db_session.commit()
    db_session.refresh(running_job)

    response = await app_client.get(f"/api/v1/jobs/{running_job.id}/results")
    assert response.status_code == 400  # Bad Request or Conflict, indicating job not ready
    assert response.json()["detail"] == "Job is not in a final state (COMPLETED or FAILED)."


@pytest.mark.asyncio
async def test_get_job_results_non_existent(app_client: AsyncClient):
    """
    Test GET /jobs/{job_id}/results for a job that does not exist.
    """
    non_existent_job_id = uuid.uuid4()
    response = await app_client.get(f"/api/v1/jobs/{non_existent_job_id}/results")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"