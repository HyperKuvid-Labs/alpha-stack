import pytest
import os
from pathlib import Path
import sanchay_core # The compiled Rust extension module

# Helper function to create dummy files for tests
def create_dummy_file(path: Path, content: str = "", byte_size: int = None):
    """
    Creates a dummy file with specified content or padded to a specific byte size.
    If byte_size is specified, content is padded with null bytes.
    """
    if byte_size is not None:
        # Encode content and pad with null bytes to reach target size
        encoded_content = content.encode('utf-8')
        if len(encoded_content) > byte_size:
            # Truncate if content is already too large
            actual_bytes = encoded_content[:byte_size]
        else:
            # Pad with null bytes
            padding_needed = byte_size - len(encoded_content)
            actual_bytes = encoded_content + b'\0' * padding_needed
    else:
        actual_bytes = content.encode('utf-8') # Default to UTF-8 encoded bytes

    path.write_bytes(actual_bytes)
    return path

# --- Basic Functionality Tests (demonstrative examples) ---

def test_add_numbers_positive():
    """Tests simple integer addition exposed by Rust."""
    result = sanchay_core.add_numbers(5, 3)
    assert result == 8

def test_add_numbers_negative():
    """Tests integer addition with negative numbers exposed by Rust."""
    result = sanchay_core.add_numbers(-5, 3)
    assert result == -2

def test_reverse_string_simple():
    """Tests string reversal with a simple word exposed by Rust."""
    result = sanchay_core.reverse_string("hello")
    assert result == "olleh"

def test_reverse_string_empty():
    """Tests string reversal with an empty string exposed by Rust."""
    result = sanchay_core.reverse_string("")
    assert result == ""

def test_reverse_string_unicode():
    """Tests string reversal with Unicode characters exposed by Rust."""
    result = sanchay_core.reverse_string("你好世界")
    assert result == "界世好你"

# --- Directory Processing Tests ---

def test_get_directory_summary_basic(tmp_path: Path):
    """
    Tests getting a basic summary of a directory, including file counts,
    directory counts, and total size.
    """
    # Create a test directory structure
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Create files with known byte sizes
    create_dummy_file(dir_a / "file1.txt", "content1", byte_size=8)
    create_dummy_file(dir_a / "file2.log", "some log data", byte_size=14)
    create_dummy_file(dir_b / "image.jpg", "binary_data_here", byte_size=17)
    create_dummy_file(tmp_path / "root_file.txt", "root content", byte_size=12)

    # Call the Rust function
    summary = sanchay_core.get_directory_summary(str(tmp_path))

    # Assertions
    assert isinstance(summary, dict)
    assert summary.get("total_files") == 4
    # Expected directories: tmp_path (root), dir_a, dir_b = 3
    assert summary.get("total_directories") == 3
    assert summary.get("total_size_bytes") == 8 + 14 + 17 + 12 # Sum of file sizes
    assert summary.get("processed_count") == 4 # All files should be processed
    assert summary.get("errors") == [] # No errors expected in this scenario

def test_get_directory_summary_empty_dir(tmp_path: Path):
    """Tests summary for an empty directory."""
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()

    summary = sanchay_core.get_directory_summary(str(empty_dir))
    assert isinstance(summary, dict)
    assert summary.get("total_files") == 0
    assert summary.get("total_directories") == 1 # The empty_dir itself is counted
    assert summary.get("total_size_bytes") == 0
    assert summary.get("processed_count") == 0
    assert summary.get("errors") == []

def test_find_duplicate_files_by_hash_found(tmp_path: Path):
    """Tests finding duplicate files by content hash."""
    # Create test files with duplicates
    dir1 = tmp_path / "folder1"
    dir2 = tmp_path / "folder2"
    dir1.mkdir()
    dir2.mkdir()

    content_a = "This is file A content."
    content_b = "This is file B content."
    content_c = "Unique content here."

    file_a1 = create_dummy_file(dir1 / "file_a_1.txt", content_a)
    file_a2 = create_dummy_file(dir2 / "file_a_2.txt", content_a) # Duplicate of file_a1
    file_b1 = create_dummy_file(dir1 / "file_b_1.log", content_b)
    file_c1 = create_dummy_file(dir2 / "file_c_1.txt", content_c)
    file_b2 = create_dummy_file(dir2 / "file_b_2.log", content_b) # Duplicate of file_b1
    file_a3 = create_dummy_file(tmp_path / "file_a_3.txt", content_a) # Another duplicate of file_a1

    # Call the Rust function
    duplicates = sanchay_core.find_duplicates_by_hash(str(tmp_path))

    assert isinstance(duplicates, list)
    assert len(duplicates) == 2 # Two groups of duplicates

    # Normalize paths for comparison (Rust might return absolute, Python Path makes it easy)
    normalized_duplicates = []
    for group in duplicates:
        # Sort paths within each group to ensure consistent order
        normalized_group = sorted([Path(p) for p in group])
        normalized_duplicates.append(normalized_group)
    # Sort the groups themselves by the first path in each group for consistent test results
    normalized_duplicates.sort(key=lambda x: str(x[0]))

    expected_duplicates_group1 = sorted([file_a1, file_a2, file_a3])
    expected_duplicates_group2 = sorted([file_b1, file_b2])

    expected_normalized_duplicates = sorted([expected_duplicates_group1, expected_duplicates_group2], key=lambda x: str(x[0]))

    assert expected_normalized_duplicates == normalized_duplicates

def test_find_duplicate_files_by_hash_no_duplicates(tmp_path: Path):
    """Tests finding duplicates when none exist in the directory."""
    create_dummy_file(tmp_path / "file1.txt", "unique content 1")
    create_dummy_file(tmp_path / "file2.log", "unique content 2")
    create_dummy_file(tmp_path / "file3.pdf", "unique content 3")

    duplicates = sanchay_core.find_duplicates_by_hash(str(tmp_path))
    assert isinstance(duplicates, list)
    assert len(duplicates) == 0

def test_find_duplicate_files_by_hash_single_file(tmp_path: Path):
    """Tests finding duplicates with only a single file in the directory (should be none)."""
    create_dummy_file(tmp_path / "single.txt", "only one file")
    duplicates = sanchay_core.find_duplicates_by_hash(str(tmp_path))
    assert isinstance(duplicates, list)
    assert len(duplicates) == 0

# --- Error Handling Tests ---

def test_get_directory_summary_invalid_path():
    """Tests error handling for a non-existent path during summary generation."""
    with pytest.raises(Exception) as excinfo: # Using generic Exception, specific type depends on PyO3 mapping
        sanchay_core.get_directory_summary("/non/existent/path/12345")
    # A more specific message match is recommended if the Rust error message is stable.
    assert "Path not found" in str(excinfo.value) or "No such file or directory" in str(excinfo.value)

def test_find_duplicate_files_invalid_path():
    """Tests error handling for a non-existent path during duplicate detection."""
    with pytest.raises(Exception) as excinfo:
        sanchay_core.find_duplicates_by_hash("/another/invalid/path/67890")
    assert "Path not found" in str(excinfo.value) or "No such file or directory" in str(excinfo.value)

def test_rust_internal_error_propagation(tmp_path: Path):
    """
    Tests that internal Rust errors are correctly propagated as Python exceptions.
    This assumes a hypothetical Rust function `trigger_error_on_path` for testing purposes.
    """
    test_path = tmp_path / "will_fail_processing"
    test_path.mkdir()

    with pytest.raises(Exception) as excinfo:
        # This function should be implemented in Rust's PyO3 bindings specifically
        # to trigger a known error condition for integration testing.
        sanchay_core.trigger_error_on_path(str(test_path))
    
    # Check for a specific part of the error message from the Rust side
    # The actual message will depend on the Rust error conversion via PyO3.
    # Common error messages could be "simulated internal processing error",
    # "RustError: ...", or a specific Rust error type name.
    assert "simulated internal processing error" in str(excinfo.value) or \
           "Rust error" in str(excinfo.value) or \
           "internal error" in str(excinfo.value)