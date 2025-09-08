import pytest
import tempfile
import shutil
import subprocess
import os
import sys
from pathlib import Path

# Add the project root and src directory to sys.path for module discovery.
# This ensures that `src.sanchay_app` and its submodules can be correctly
# imported by both the test runner and the subprocess.
@pytest.fixture(scope="session", autouse=True)
def setup_pythonpath():
    """
    Sets up the Python path to ensure `src.sanchay_app` is discoverable.
    """
    # Assuming this file is at `project-sanchay/tests/e2e/test_full_scan.py`
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"

    # Insert project root and src path to the beginning of sys.path
    # This allows imports like `from src.sanchay_app.database.models import ...`
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(src_path))
    
    yield # Run tests
    
    # Clean up sys.path after tests
    sys.path.remove(str(src_path))
    sys.path.remove(str(project_root))


# Import SQLAlchemy components and application models
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
# Ensure these models exist and are accessible from `src.sanchay_app.database.models`
from src.sanchay_app.database.models import Base, FileMetadata, Job, DuplicateFilePair


@pytest.fixture(scope="function")
def temp_test_env():
    """
    Creates a temporary directory for test files, a temporary SQLite database,
    and sets up environment variables for the CLI process.
    Yields a dictionary containing paths and environment variables,
    and ensures cleanup after the test.
    """
    # Determine the project root dynamically based on the current file's location
    project_root = Path(__file__).resolve().parents[2]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        test_data_dir = temp_dir_path / "test_data"
        test_data_dir.mkdir()

        # Create sample files for scanning, including duplicates
        (test_data_dir / "file1.txt").write_text("This is content A.")
        (test_data_dir / "file2.txt").write_text("This is content B.")
        (test_data_dir / "file3_duplicate.txt").write_text("This is content A.")  # Duplicate of file1.txt
        (test_data_dir / "subdir").mkdir()
        (test_data_dir / "subdir" / "file4.txt").write_text("More content C.")
        (test_data_dir / "subdir" / "file5_duplicate_deep.txt").write_text("This is content A.") # Another duplicate

        temp_db_path = temp_dir_path / "sanchay_test.db"

        # Set environment variables for the CLI subprocess.
        # This allows the application to use the temporary database path
        # and configure logging specifically for the test run.
        env = os.environ.copy()
        env["DATABASE_PATH"] = str(temp_db_path)
        env["LOG_LEVEL"] = "DEBUG" # Enable verbose logging for test debugging

        yield {
            "test_data_dir": test_data_dir,
            "temp_db_path": temp_db_path,
            "env": env,
            "project_root": project_root
        }

        # The `TemporaryDirectory` context manager handles the cleanup of `temp_dir_path`
        # and all its contents (including test_data_dir and temp_db_path) automatically.


def test_full_directory_scan_and_duplicate_detection_cli(temp_test_env):
    """
    Performs an end-to-end test of the Sanchay application's CLI scan functionality.
    It initiates a scan of a temporary directory, including duplicate detection,
    and then verifies that the results are correctly stored in the temporary SQLite database.
    """
    test_data_dir = temp_test_env["test_data_dir"]
    temp_db_path = temp_test_env["temp_db_path"]
    env = temp_test_env["env"]
    project_root = temp_test_env["project_root"]

    # Construct the command to run the CLI.
    # We use `sys.executable -m src.sanchay_app` to ensure the correct Python
    # interpreter is used and the application's main entry point is invoked
    # as a module, mimicking how it would be run as a user.
    # The `scan` command with `--detect-duplicates` flag is used as per project requirements.
    cli_command = [
        sys.executable,  # Path to the current Python interpreter
        "-m",
        "src.sanchay_app",
        "scan",
        str(test_data_dir),
        "--detect-duplicates" # Assuming this flag enables checksumming and duplicate detection
    ]

    # Execute the CLI command.
    # `cwd=project_root` ensures that `src.sanchay_app` can be correctly imported
    # by the subprocess, as if running from the project's root directory.
    result = subprocess.run(
        cli_command,
        capture_output=True, # Capture stdout and stderr
        text=True,           # Decode stdout/stderr as text
        env=env,             # Pass the modified environment variables
        cwd=project_root     # Set the current working directory for the subprocess
    )

    # Assert that the CLI command exited successfully (return code 0).
    # Provide detailed output in case of failure for easier debugging.
    assert result.returncode == 0, \
        f"CLI scan command failed with return code {result.returncode}.\n" \
        f"Stderr:\n{result.stderr}\nStdout:\n{result.stdout}"

    # Verify key messages in the CLI's standard output.
    assert "Scan initiated for path" in result.stdout
    assert "Scan completed successfully" in result.stdout or "Processed files" in result.stdout
    # Depending on exact CLI output, ensure duplicate detection was acknowledged.
    assert "Duplicates found" in result.stdout or "No duplicates found" in result.stdout 

    # Verify that the temporary SQLite database file was created by the application.
    assert temp_db_path.exists(), "Database file was not created by the application as expected."

    # Establish an SQLAlchemy session to query the temporary database.
    # This allows us to verify the data persisted by the application's core logic.
    engine = create_engine(f"sqlite:///{temp_db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Use SQLAlchemy's inspector to check if tables were created.
        # This confirms the application's database initialization/migration logic.
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "file_metadata" in table_names, "FileMetadata table not found in the temporary database."
        assert "jobs" in table_names, "Jobs table not found in the temporary database."
        assert "duplicate_file_pairs" in table_names, "DuplicateFilePairs table not found in the temporary database."


        # --- 1. Verify FileMetadata entries ---
        file_metadata_entries = session.query(FileMetadata).all()
        # We created 5 files: file1, file2, file3_duplicate, file4, file5_duplicate_deep.
        assert len(file_metadata_entries) == 5, \
            f"Expected 5 files in metadata, but found {len(file_metadata_entries)}."

        # Retrieve specific file entries to verify checksums for duplicates.
        file1_entry = session.query(FileMetadata).filter(FileMetadata.name == "file1.txt").first()
        file3_entry = session.query(FileMetadata).filter(FileMetadata.name == "file3_duplicate.txt").first()
        file5_entry = session.query(FileMetadata).filter(FileMetadata.name == "file5_duplicate_deep.txt").first()

        assert file1_entry is not None, "file1.txt entry not found in FileMetadata."
        assert file3_entry is not None, "file3_duplicate.txt entry not found in FileMetadata."
        assert file5_entry is not None, "file5_duplicate_deep.txt entry not found in FileMetadata."

        # Verify that all duplicate files (file1, file3, file5) have the same checksum.
        assert file1_entry.checksum == file3_entry.checksum, \
            "Checksums for 'file1.txt' and 'file3_duplicate.txt' should be identical."
        assert file1_entry.checksum == file5_entry.checksum, \
            "Checksums for 'file1.txt' and 'file5_duplicate_deep.txt' should be identical."


        # --- 2. Verify Job status ---
        # Retrieve the most recent job entry from the database.
        latest_job = session.query(Job).order_by(Job.id.desc()).first()
        assert latest_job is not None, "No job entry found in the database after scan."
        assert latest_job.status == "completed", \
            f"Expected job status to be 'completed', but was '{latest_job.status}'."
        assert latest_job.target_path == str(test_data_dir), \
            f"Job target path mismatch: expected '{test_data_dir}', got '{latest_job.target_path}'."


        # --- 3. Verify DuplicateFilePair entries ---
        duplicate_pairs = session.query(DuplicateFilePair).all()
        # We have three files with identical content (file1, file3, file5).
        # If the application stores unique pairs, we would expect 3 pairs:
        # (file1, file3), (file1, file5), (file3, file5).
        # A simple check for at least 2 pairs confirms duplicate detection worked.
        assert len(duplicate_pairs) >= 2, \
            f"Expected at least 2 duplicate pairs to be recorded, but found {len(duplicate_pairs)}. " \
            "This suggests duplicate detection or storage might be incomplete."

        # Example of a more specific check: Ensure file1.txt is part of at least one recorded duplicate pair.
        found_file1_as_duplicate = False
        for pair in duplicate_pairs:
            # Check if file1_entry's ID is one of the file IDs in the pair
            if pair.file_id_1 == file1_entry.id or pair.file_id_2 == file1_entry.id:
                found_file1_as_duplicate = True
                break
        assert found_file1_as_duplicate, "file1.txt was expected to be recorded as part of a duplicate pair."

    finally:
        # Always close the SQLAlchemy session to release database resources.
        session.close()