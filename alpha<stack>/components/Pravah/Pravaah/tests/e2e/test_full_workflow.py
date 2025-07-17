import pytest
import httpx
import time
from pathlib import Path
import json
import os

# Define the API version for consistent access
API_VERSION = "/api/v1"

@pytest.mark.e2e
def test_file_processing_workflow_success(
    httpx_client: httpx.Client,
    temp_input_dir: Path,
    temp_output_dir: Path
):
    """
    End-to-end test for a successful file processing workflow:
    1. Creates dummy input files.
    2. Submits a job to the API.
    3. Polls the job status until completion.
    4. Verifies the output files in the designated output directory.
    5. Retrieves and validates job results from the API.
    """
    # 1. Setup: Create dummy input files in the temporary input directory
    file_contents = {
        "document_a.txt": "This is the content of document A.\nIt has multiple lines for testing.",
        "data_b.csv": "col1,col2,col3\nval1_a,val1_b,val1_c\nval2_a,val2_b,val2_c",
        "log_c.log": "INFO: First log entry\nERROR: Something went wrong\nDEBUG: Debugging message"
    }

    for filename, content in file_contents.items():
        file_path = temp_input_dir / filename
        file_path.write_text(content)
        print(f"Created input file: {file_path}")

    # 2. Submit a new job to "copy" the files
    # The 'processing_config' type 'copy_files' is assumed to be handled by the Rust engine
    # to simply transfer files from input_path to output_path.
    job_payload = {
        "input_path": str(temp_input_dir),
        "output_path": str(temp_output_dir),
        "processing_config": {
            "type": "copy_files",
            "options": {} # No specific options for a simple copy
        }
    }
    print(f"\nSubmitting job with payload: {job_payload}")
    response = httpx_client.post(f"{API_VERSION}/jobs", json=job_payload)

    assert response.status_code == 200, \
        f"Expected 200 OK for job submission, got {response.status_code}: {response.text}"

    job_response = response.json()
    job_id = job_response.get("job_id")
    initial_status = job_response.get("status")

    assert job_id is not None, "Job ID not found in response."
    assert initial_status in ["PENDING", "ACCEPTED"], f"Unexpected initial job status: {initial_status}"
    print(f"Job submitted successfully. Job ID: {job_id}, Initial status: {initial_status}")

    # 3. Poll for job completion
    max_retries = 30
    delay_seconds = 0.5 # Shorter delay for faster test execution, adjust if needed
    job_status = None
    final_job_details = None

    for i in range(max_retries):
        print(f"Polling job {job_id} status (attempt {i+1}/{max_retries})...")
        status_response = httpx_client.get(f"{API_VERSION}/jobs/{job_id}")
        assert status_response.status_code == 200, \
            f"Failed to get job {job_id} status: {status_response.status_code}: {status_response.text}"

        job_details = status_response.json()
        job_status = job_details.get("status")
        print(f"Job {job_id} current status: {job_status}")

        if job_status in ["COMPLETED", "FAILED"]:
            final_job_details = job_details
            break
        time.sleep(delay_seconds)
    else:
        pytest.fail(f"Job {job_id} did not complete within {max_retries * delay_seconds} seconds. "
                    f"Final status observed: {job_status}")

    assert job_status == "COMPLETED", \
        f"Job {job_id} failed with status: {job_status}. Details: {json.dumps(final_job_details, indent=2)}"
    assert final_job_details is not None, "Job details not retrieved after completion."

    # 4. Verify output files
    assert temp_output_dir.exists(), f"Output directory {temp_output_dir} does not exist."
    assert temp_output_dir.is_dir(), f"Output path {temp_output_dir} is not a directory."

    output_files_found = list(temp_output_dir.iterdir())
    print(f"Files found in output directory {temp_output_dir}: {[f.name for f in output_files_found]}")

    assert len(output_files_found) == len(file_contents), \
        f"Expected {len(file_contents)} output files, but found {len(output_files_found)}."

    for filename, original_content in file_contents.items():
        output_file_path = temp_output_dir / filename
        assert output_file_path.exists(), f"Output file '{filename}' was not found in {temp_output_dir}."
        assert output_file_path.read_text() == original_content, \
            f"Content mismatch for output file '{filename}'. Expected:\n{original_content}\nGot:\n{output_file_path.read_text()}"
        print(f"Verified content of output file: {output_file_path.name}")

    # 5. Retrieve and validate job results from the API
    results_response = httpx_client.get(f"{API_VERSION}/jobs/{job_id}/results")
    assert results_response.status_code == 200, \
        f"Expected 200 OK for retrieving results, got {results_response.status_code}: {results_response.text}"
    
    job_results = results_response.json()
    print(f"Job results from API: {json.dumps(job_results, indent=2)}")

    # For a 'copy_files' operation, the results might list the files that were processed.
    # The exact schema depends on Pravah's `schemas.py` and Rust engine's output.
    # Assuming 'processed_files' is a list of dictionaries, each with 'original_path' and 'output_path'.
    assert "processed_files" in job_results, "'processed_files' key missing in job results."
    assert isinstance(job_results["processed_files"], list), "'processed_files' is not a list."
    assert len(job_results["processed_files"]) == len(file_contents), \
        f"Expected {len(file_contents)} entries in processed_files, got {len(job_results['processed_files'])}."

    processed_filenames = {Path(f["original_path"]).name for f in job_results["processed_files"]}
    for expected_filename in file_contents.keys():
        assert expected_filename in processed_filenames, \
            f"Expected processed file '{expected_filename}' not found in API results' processed_files."
    print("Successfully verified job results via API.")


@pytest.mark.e2e
def test_job_submission_with_invalid_payload(httpx_client: httpx.Client):
    """
    Test submitting a job with various invalid payloads to ensure
    FastAPI's validation (via Pydantic) works correctly, returning 422.
    """
    invalid_payloads = [
        {}, # Missing all required fields
        {"input_path": "/path/to/input", "output_path": "/path/to/output"}, # Missing processing_config
        {"input_path": "invalid_path", "output_path": "/path/to/output", "processing_config": {"type": "copy_files"}}, # Invalid path format (FastAPI might auto-fix, but good to check)
        {"input_path": "/path/to/input", "output_path": "/path/to/output", "processing_config": {"type": "unknown_operation"}}, # Unknown processing type
        {"input_path": 123, "output_path": "output", "processing_config": {"type": "copy_files"}}, # Incorrect type for input_path
    ]

    for i, payload in enumerate(invalid_payloads):
        print(f"\nTesting invalid payload {i+1}/{len(invalid_payloads)}: {json.dumps(payload)}")
        response = httpx_client.post(f"{API_VERSION}/jobs", json=payload)

        assert response.status_code == 422, \
            f"Expected 422 Unprocessable Entity for invalid payload {i+1}, got {response.status_code}: {response.text}"

        error_details = response.json()
        assert "detail" in error_details, f"Error detail missing for payload {i+1}: {error_details}"
        assert isinstance(error_details["detail"], list) or isinstance(error_details["detail"], str), \
            f"Unexpected format for error detail for payload {i+1}: {error_details['detail']}"
        print(f"Received expected 422 error: {error_details['detail']}")

@pytest.mark.e2e
def test_get_nonexistent_job_status(httpx_client: httpx.Client):
    """
    Test requesting the status of a non-existent job ID.
    Should result in a 404 Not Found.
    """
    non_existent_job_id = "nonexistent-job-12345"
    print(f"\nAttempting to get status for non-existent job ID: {non_existent_job_id}")
    response = httpx_client.get(f"{API_VERSION}/jobs/{non_existent_job_id}")

    assert response.status_code == 404, \
        f"Expected 404 Not Found for non-existent job, got {response.status_code}: {response.text}"
    
    error_details = response.json()
    assert "detail" in error_details
    assert "Job not found" in error_details["detail"]
    print(f"Received expected 404 error: {error_details['detail']}")

@pytest.mark.e2e
def test_get_nonexistent_job_results(httpx_client: httpx.Client):
    """
    Test requesting the results of a non-existent job ID.
    Should result in a 404 Not Found.
    """
    non_existent_job_id = "another-nonexistent-job-67890"
    print(f"\nAttempting to get results for non-existent job ID: {non_existent_job_id}")
    response = httpx_client.get(f"{API_VERSION}/jobs/{non_existent_job_id}/results")

    assert response.status_code == 404, \
        f"Expected 404 Not Found for non-existent job results, got {response.status_code}: {response.text}"
    
    error_details = response.json()
    assert "detail" in error_details
    assert "Job not found" in error_details["detail"]
    print(f"Received expected 404 error: {error_details['detail']}")