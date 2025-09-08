import pytest
from pathlib import Path
from src.sanchay_app.core.job_manager import JobManager, JobState
from typing import Dict, Any


@pytest.fixture
def job_manager() -> JobManager:
    """Provides a fresh JobManager instance for each test."""
    return JobManager()


def test_create_job(job_manager: JobManager):
    task_type = "file_scan"
    path = Path("/tmp/test_dir")
    job_id = job_manager.create_job(task_type, path)

    assert isinstance(job_id, str)
    assert len(job_id) > 0

    status = job_manager.get_job_status(job_id)
    assert status.job_id == job_id
    assert status.task_type == task_type
    assert status.path == path
    assert status.state == JobState.PENDING
    assert status.progress_current == 0
    assert status.progress_total == 100
    assert status.status_message == "Job created"
    assert status.start_time is None
    assert status.end_time is None
    assert status.results is None
    assert status.error_message is None


def test_get_non_existent_job(job_manager: JobManager):
    with pytest.raises(KeyError, match="Job with ID non-existent-id not found."):
        job_manager.get_job_status("non-existent-id")


def test_start_job(job_manager: JobManager):
    job_id = job_manager.create_job("checksum", Path("/data/files"))
    job_manager.start_job(job_id)

    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.RUNNING
    assert status.start_time is not None
    assert status.status_message == "Job started"

    # Cannot start a job already running
    with pytest.raises(ValueError, match="cannot be started from state RUNNING"):
        job_manager.start_job(job_id)


def test_update_progress(job_manager: JobManager):
    job_id = job_manager.create_job("count", Path("/path/to/docs"))
    job_manager.start_job(job_id)

    job_manager.update_progress(job_id, 10, 100, "Processing item 10 of 100")
    status = job_manager.get_job_status(job_id)
    assert status.progress_current == 10
    assert status.progress_total == 100
    assert status.status_message == "Processing item 10 of 100"

    job_manager.update_progress(job_id, 50, 100)  # Update without message
    status = job_manager.get_job_status(job_id)
    assert status.progress_current == 50
    # Status message should not change if not provided
    assert status.status_message == "Processing item 10 of 100"

    # Cannot update progress if not running
    job_manager.complete_job(job_id, {"count": 100})
    with pytest.raises(ValueError, match="cannot update progress in state COMPLETED"):
        job_manager.update_progress(job_id, 60, 100)

    # Test invalid progress values
    job_id_invalid = job_manager.create_job("invalid_progress", Path("/path"))
    job_manager.start_job(job_id_invalid)
    with pytest.raises(ValueError, match="Progress current .* must be between 0 and total"):
        job_manager.update_progress(job_id_invalid, -1, 100)
    with pytest.raises(ValueError, match="Progress current .* must be between 0 and total"):
        job_manager.update_progress(job_id_invalid, 101, 100)


def test_complete_job(job_manager: JobManager):
    job_id = job_manager.create_job("deduplicate", Path("/images"))
    job_manager.start_job(job_id)
    job_manager.update_progress(job_id, 90, 100)

    results = {"duplicates_found": 5, "total_files": 1000}
    job_manager.complete_job(job_id, results)

    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.COMPLETED
    assert status.end_time is not None
    assert status.results == results
    assert status.status_message == "Job completed successfully"
    assert status.progress_current == 90  # Progress should remain as last updated

    # Cannot complete an already completed job (or pending/stopped/failed)
    with pytest.raises(ValueError, match="cannot be completed from state COMPLETED"):
        job_manager.complete_job(job_id, {})


def test_fail_job(job_manager: JobManager):
    job_id = job_manager.create_job("upload", Path("/uploads"))
    job_manager.start_job(job_id)
    job_manager.update_progress(job_id, 20, 100)

    error_msg = "Network connection lost"
    job_manager.fail_job(job_id, error_msg)

    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.FAILED
    assert status.end_time is not None
    assert status.error_message == error_msg
    assert status.status_message == f"Job failed: {error_msg}"

    # Cannot fail an already completed job
    job_id_completed = job_manager.create_job("success_upload", Path("/completed"))
    job_manager.start_job(job_id_completed)
    job_manager.complete_job(job_id_completed, {})
    with pytest.raises(ValueError, match="cannot be failed from state COMPLETED"):
        job_manager.fail_job(job_id_completed, "Should not fail")


def test_stop_job(job_manager: JobManager):
    job_id = job_manager.create_job("large_scan", Path("/deep/folder"))
    job_manager.start_job(job_id)
    job_manager.update_progress(job_id, 5, 1000, "Scanning files...")

    job_manager.stop_job(job_id)
    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.STOPPED
    assert status.end_time is not None
    assert status.status_message == "Job stopped by user"

    # Can restart a stopped job
    job_manager.start_job(job_id)
    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.RUNNING
    assert status.start_time is not None  # Start time should be updated on restart

    # Cannot stop a completed or failed job
    job_id_completed = job_manager.create_job("complete_stop", Path("/comp"))
    job_manager.start_job(job_id_completed)
    job_manager.complete_job(job_id_completed, {})
    with pytest.raises(ValueError, match="cannot be stopped from state COMPLETED"):
        job_manager.stop_job(job_id_completed)

    job_id_failed = job_manager.create_job("failed_stop", Path("/fail"))
    job_manager.start_job(job_id_failed)
    job_manager.fail_job(job_id_failed, "error")
    with pytest.raises(ValueError, match="cannot be stopped from state FAILED"):
        job_manager.stop_job(job_id_failed)


def test_list_jobs(job_manager: JobManager):
    job_id1 = job_manager.create_job("type_a", Path("/a"))
    job_manager.start_job(job_id1)
    job_manager.update_progress(job_id1, 10, 100)

    job_id2 = job_manager.create_job("type_b", Path("/b"))
    job_manager.start_job(job_id2)
    job_manager.complete_job(job_id2, {"result": "ok"})

    all_jobs = job_manager.list_jobs()
    assert len(all_jobs) == 2
    assert job_id1 in all_jobs
    assert job_id2 in all_jobs

    assert all_jobs[job_id1].state == JobState.RUNNING
    assert all_jobs[job_id2].state == JobState.COMPLETED

    # Ensure list_jobs returns a copy, not the internal dictionary
    original_len = len(job_manager.list_jobs())
    del all_jobs[job_id1]
    assert len(job_manager.list_jobs()) == original_len  # Internal dict should be unaffected


def test_job_state_transitions(job_manager: JobManager):
    job_id = job_manager.create_job("transitions", Path("/test"))

    # Initial state
    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.PENDING

    # PENDING -> RUNNING
    job_manager.start_job(job_id)
    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.RUNNING

    # RUNNING -> COMPLETED
    job_manager.complete_job(job_id, {})
    status = job_manager.get_job_status(job_id)
    assert status.state == JobState.COMPLETED

    # COMPLETED -> FAILED (should raise error)
    with pytest.raises(ValueError, match="cannot be failed from state COMPLETED"):
        job_manager.fail_job(job_id, "error")

    # Reset for another path: PENDING -> FAILED
    job_id_2 = job_manager.create_job("fail_early", Path("/test2"))
    job_manager.fail_job(job_id_2, "early failure")
    status_2 = job_manager.get_job_status(job_id_2)
    assert status_2.state == JobState.FAILED

    # FAILED -> START (should raise error)
    with pytest.raises(ValueError, match="cannot be started from state FAILED"):
        job_manager.start_job(job_id_2)

    # PENDING -> STOPPED
    job_id_3 = job_manager.create_job("stop_early", Path("/test3"))
    job_manager.stop_job(job_id_3)
    status_3 = job_manager.get_job_status(job_id_3)
    assert status_3.state == JobState.STOPPED

    # STOPPED -> RUNNING (should be allowed)
    job_manager.start_job(job_id_3)
    status_3 = job_manager.get_job_status(job_id_3)
    assert status_3.state == JobState.RUNNING

    # RUNNING -> STOPPED
    job_manager.stop_job(job_id_3)
    status_3 = job_manager.get_job_status(job_id_3)
    assert status_3.state == JobState.STOPPED