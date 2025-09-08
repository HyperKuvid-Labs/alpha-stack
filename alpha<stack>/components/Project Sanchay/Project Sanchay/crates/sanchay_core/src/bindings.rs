use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::wrap_pyfunction;

// Import core logic from other modules within sanchay_core
use crate::error::SanchayCoreError;
use crate::file_processor::ChecksumAlgorithm;
use crate::walker;

/// A simple greeting function for testing Python-Rust integration.
#[pyfunction]
fn greet() -> PyResult<String> {
    Ok("Hello from Sanchay Rust core!".to_string())
}

/// Scans a directory and collects basic metadata for all files.
///
/// Args:
///     directory_path (str): The path to the directory to scan.
///     include_checksum (bool, optional): Whether to calculate checksums for files. Defaults to False.
///     checksum_algorithm (str, optional): The algorithm to use for checksums (e.g., "sha256", "md5").
///                                         Defaults to "sha256".
///
/// Returns:
///     list[dict]: A list of dictionaries, each representing file metadata.
///     Each dict contains 'path', 'size', 'last_modified' (Unix timestamp in ms), and 'checksum' (optional).
///
/// Raises:
///     ValueError: If an invalid checksum algorithm is provided or if a Rust core error occurs.
///     OSError: If an I/O related error occurs during directory traversal or file access.
#[pyfunction]
fn get_file_metadata(
    py: Python,
    directory_path: &str,
    include_checksum: Option<bool>,
    checksum_algorithm: Option<&str>,
) -> PyResult<Py<PyList>> {
    let include_checksum = include_checksum.unwrap_or(false);
    let algorithm = checksum_algorithm
        .map(|s| ChecksumAlgorithm::from_str(s))
        .transpose()?; // Automatically converts SanchayCoreError to PyErr
    let algorithm = algorithm.unwrap_or(ChecksumAlgorithm::SHA256); // Default

    let result = py.allow_threads(move || {
        walker::scan_directory_for_metadata(directory_path, include_checksum, algorithm)
    });

    match result {
        Ok(metadata_vec) => {
            let py_list = PyList::empty(py);
            for meta in metadata_vec {
                let dict = PyDict::new(py);
                dict.set_item("path", meta.path.to_string_lossy().into_owned())?;
                dict.set_item("size", meta.size)?;

                // Convert SystemTime to milliseconds Unix timestamp
                let last_modified_ms = meta
                    .last_modified
                    .map(|t| {
                        t.duration_since(std::time::UNIX_EPOCH)
                            .map(|d| d.as_millis() as u64)
                            .unwrap_or(0) // Default to 0 if time is before epoch
                    })
                    .unwrap_or(0); // Default to 0 if SystemTime is not available
                dict.set_item("last_modified", last_modified_ms)?;
                dict.set_item("checksum", meta.checksum)?; // Option<String> directly maps to None/String in Python
                py_list.append(dict)?;
            }
            Ok(py_list.into())
        }
        Err(e) => Err(e.into()), // Convert SanchayCoreError to PyErr (PyValueError or PyIOError via From trait)
    }
}

/// Finds duplicate files within a given directory based on their content hash.
///
/// Args:
///     directory_path (str): The path to the directory to scan.
///     checksum_algorithm (str, optional): The algorithm to use for checksums (e.g., "sha256", "md5").
///                                         Defaults to "sha256".
///
/// Returns:
///     list[list[str]]: A list of lists, where each inner list contains paths of duplicate files.
///                      Each inner list represents a group of files that are identical by hash.
///
/// Raises:
///     ValueError: If an invalid checksum algorithm is provided or if a Rust core error occurs.
///     OSError: If an I/O related error occurs during directory traversal or file access.
#[pyfunction]
fn find_duplicates(
    py: Python,
    directory_path: &str,
    checksum_algorithm: Option<&str>,
) -> PyResult<Py<PyList>> {
    let algorithm = checksum_algorithm
        .map(|s| ChecksumAlgorithm::from_str(s))
        .transpose()?;
    let algorithm = algorithm.unwrap_or(ChecksumAlgorithm::SHA256);

    let result = py.allow_threads(move || {
        walker::find_duplicate_files_in_directory(directory_path, algorithm)
    });

    match result {
        Ok(duplicate_groups) => {
            let py_list = PyList::empty(py);
            for group in duplicate_groups {
                let inner_list = PyList::empty(py);
                for path in group {
                    inner_list.append(path.to_string_lossy().into_owned())?;
                }
                py_list.append(inner_list)?;
            }
            Ok(py_list.into())
        }
        Err(e) => Err(e.into()), // Convert SanchayCoreError to PyErr
    }
}

/// A Python module implemented in Rust, providing high-performance file processing capabilities.
///
/// This module exposes functions to scan directories, collect file metadata, and find duplicate files
/// using Rust's speed and concurrency features.
#[pymodule]
fn sanchay_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(greet, m)?)?;
    m.add_function(wrap_pyfunction!(get_file_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(find_duplicates, m)?)?;

    // Optionally, add custom Python exceptions if a more granular error handling
    // is desired on the Python side than PyValueError/PyIOError.
    // For example: m.add("SanchayCoreError", py.get_type::<PyValueError>())?;

    Ok(())
}