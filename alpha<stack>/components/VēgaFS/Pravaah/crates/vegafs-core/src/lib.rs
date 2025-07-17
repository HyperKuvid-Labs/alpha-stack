use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::IntoPyErr;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// Import custom error types from error.rs
mod error;
use error::{CoreError, Result};

// Import file operation logic from file_ops.rs
mod file_ops;

/// Represents the summary of a directory.
/// This struct will be exposed to Python.
#[pyclass(get_all, name = "DirectorySummary")]
#[derive(Debug, Serialize, Deserialize)]
pub struct DirectorySummary {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub total_files: usize,
    #[pyo3(get)]
    pub total_directories: usize,
    #[pyo3(get)]
    pub total_size_bytes: u64,
    #[pyo3(get)]
    pub largest_files: Vec<(String, u64)>, // (path, size)
    #[pyo3(get)]
    pub file_type_counts: HashMap<String, usize>, // (extension, count)
}

#[pymethods]
impl DirectorySummary {
    #[new]
    fn new(
        path: String,
        total_files: usize,
        total_directories: usize,
        total_size_bytes: u64,
        largest_files: Vec<(String, u64)>,
        file_type_counts: HashMap<String, usize>,
    ) -> Self {
        DirectorySummary {
            path,
            total_files,
            total_directories,
            total_size_bytes,
            largest_files,
            file_type_counts,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "DirectorySummary(path='{}', files={}, dirs={}, size={})",
            self.path, self.total_files, self.total_directories, self.total_size_bytes
        )
    }

    fn __str__(&self) -> String {
        self.__repr__()
    }
}

/// Asynchronously summarizes the contents of a given directory.
/// This function is exposed to Python and leverages Tokio for async I/O.
#[pyfunction]
fn summarize_directory_async(py: Python, path: String) -> PyResult<PyObject> {
    pyo3_asyncio::tokio::future_into_py(py, async move {
        let result = file_ops::summarize_directory(&path).await;
        match result {
            Ok(summary) => Ok(Python::with_gil(|py| summary.into_py(py))),
            Err(e) => Err(e.into_pyerr()), // Convert Rust error to Python error
        }
    })
}

/// Asynchronously counts lines in files within a directory, optionally filtered by extensions.
/// This function is exposed to Python and leverages Tokio for async I/O.
#[pyfunction]
fn count_lines_in_files_async(
    py: Python,
    path: String,
    extensions: Vec<String>,
) -> PyResult<PyObject> {
    pyo3_asyncio::tokio::future_into_py(py, async move {
        let result = file_ops::count_lines_in_files(&path, &extensions).await;
        match result {
            Ok(counts) => Ok(Python::with_gil(|py| counts.into_py(py))),
            Err(e) => Err(e.into_pyerr()),
        }
    })
}

/// The PyO3 module definition. This is the entry point for Python.
/// It defines the module name and registers the classes and functions
/// that are exposed to the Python interpreter.
#[pymodule]
fn vegafs_core(py: Python, m: &PyModule) -> PyResult<()> {
    // Add classes to the module
    m.add_class::<DirectorySummary>()?;

    // Add functions to the module
    m.add_function(wrap_pyfunction!(summarize_directory_async, m)?)?;
    m.add_function(wrap_pyfunction!(count_lines_in_files_async, m)?)?;

    // Export a custom Python error type for Rust CoreError.
    // This allows Python code to catch specific errors originating from the Rust core.
    m.add(
        "CoreError",
        py.get_type::<PyValueError>() // Map all Rust CoreErrors to Python ValueError for simplicity
            .call1((format!("VēgaFS Core Error Base Exception"),))?,
    )?;

    Ok(())
}

// Implement the `IntoPyErr` trait for `CoreError`.
// This allows any `CoreError` to be easily converted into a `PyErr`,
// which can then be raised as an exception in Python.
impl IntoPyErr for CoreError {
    fn into_pyerr(self) -> PyErr {
        PyValueError::new_err(format!("VēgaFS Core Error: {}", self))
    }
}