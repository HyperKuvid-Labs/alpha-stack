use pyo3::prelude::*;
use pyo3::exceptions::PyException;
use pyo3::wrap_pyfunction;

use tokio::runtime::Runtime;

// Internal modules, declared here to be part of the crate
mod engine;
mod error;
mod models;

// Import the core Rust types for use in PyO3 function signatures.
// These types must derive `serde::Serialize` and `serde::Deserialize`
// for PyO3's automatic conversion feature to work.
use models::{JobParameters, ProcessingResult};
use error::PravahCoreError;

// Define a custom Python exception type that extends Python's base Exception.
// This allows specific Rust errors to map to a well-defined Python exception,
// providing better error handling and introspection on the Python side.
#[pyclass(extends=PyException)]
#[derive(Debug)]
pub struct PravahCorePyException {
    // No fields needed here, as the message will be passed to the base exception.
    // This struct simply serves as a distinct type for the Python exception.
}

// Implement the `__new__` method for our custom Python exception.
// This is how the Python exception object will be constructed when raised from Rust.
#[pymethods]
impl PravahCorePyException {
    #[new]
    fn new(msg: String) -> PyResult<(Self, Py<PyAny>)> {
        // Construct the base `PyException` with the provided message.
        let err = PyException::new_err(msg);
        // Return our custom exception type along with the base exception instance.
        Ok((PravahCorePyException {}, err.into_py(err.py())))
    }
}

// Implement the `From` trait to convert our `PravahCoreError` (Rust enum)
// into a `PyErr` (PyO3's error type). This is crucial for seamless
// error propagation from the Rust core to the Python application.
impl From<PravahCoreError> for PyErr {
    fn from(err: PravahCoreError) -> PyErr {
        // Use our custom Python exception type to wrap the Rust error message.
        // The `format!("{}", err)` uses the `Display` implementation of `PravahCoreError`.
        PravahCorePyException::new_err(format!("{}", err))
    }
}

/// A Python function that initiates a high-performance file processing job in the Pravah Rust core.
///
/// This function serves as the primary entry point from Python to the Rust engine.
/// It is exposed as a synchronous function to Python, but internally it manages
/// its own asynchronous operations using a Tokio runtime. This design allows the
/// Rust core to handle extensive I/O and CPU-bound tasks efficiently without
/// blocking the Python event loop if used within an `asyncio` context, while
/// providing a simple blocking interface for synchronous Python calls.
///
/// Args:
///     params (models.JobParameters): An object (converted from a Python dictionary or Pydantic model)
///                                    containing the parameters for the processing job, including
///                                    input/output paths, processing options, and job metadata.
///
/// Returns:
///     models.ProcessingResult: An object (converted to a Python dictionary) containing the
///                              comprehensive summary of the completed processing job, including
///                              overall status, counts of files scanned and processed, and
///                              detailed results for individual files.
///
/// Raises:
///     PravahCorePyException: If any error occurs during the processing within the Rust core,
///                            such as I/O errors (e.g., file not found, permission denied),
///                            invalid input parameters, or issues with the underlying Tokio runtime.
#[pyfunction]
#[pyo3(name = "process_files")] // Exposes the function to Python under this name
fn py_process_files(_py: Python, params: JobParameters) -> PyResult<ProcessingResult> {
    // Initialize a new Tokio runtime.
    // This runtime will execute all asynchronous Rust code within this function call.
    // `block_on` will block the current thread until the async operation completes,
    // which is suitable for long-running batch processing jobs.
    let rt = Runtime::new().map_err(|e| {
        // Convert `std::io::Error` (from `Runtime::new`) into our custom `PravahCoreError`
        // and then into a `PyErr` (PravahCorePyException).
        PravahCoreError::TokioRuntime(format!("Failed to create Tokio runtime: {}", e))
    })?;

    // Block on the asynchronous processing function provided by the `engine` module.
    // This is where the core file scanning, parallel processing, and data manipulation
    // logic will be executed.
    let result = rt.block_on(async {
        engine::process_files_async(params).await
    });

    // Handle any `PravahCoreError` returned by the Rust engine.
    // The `map_err(PyErr::from)` automatically converts the Rust error into a `PyErr`
    // (using our `From<PravahCoreError> for PyErr` implementation) and propagates it
    // as a Python exception.
    let rust_result = result.map_err(PyErr::from)?;

    // Return the `ProcessingResult`. PyO3, with the `serde` feature enabled, will
    // automatically serialize this Rust struct into a Python dictionary, assuming
    // `ProcessingResult` and its nested types implement `serde::Serialize`.
    Ok(rust_result)
}

/// Initializes the `_pravah_core` Rust library as a Python module.
///
/// This function is the entry point for PyO3, executed when the Python module
/// `pravah_core` (imported as `_pravah_core` in Python, according to standard practices
/// for native extensions) is loaded. It performs necessary setup tasks:
///
/// 1. Adds our custom `PravahCorePyException` class to the module, making it
///    accessible and catchable in Python.
/// 2. Exposes the `process_files` Rust function to Python.
/// 3. Sets a docstring for the Python module for better documentation.
#[pymodule]
fn _pravah_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // Add our custom Python exception class to the module.
    // Python code can then `from pravah_core import PravahCorePyException`
    // and catch it.
    m.add_class::<PravahCorePyException>()?;

    // Add the `py_process_files` function to the module.
    // `wrap_pyfunction!` handles the boilerplate of creating a Python callable.
    m.add_function(wrap_pyfunction!(py_process_files, m)?)?;

    // Set a docstring for the Python module itself.
    m.setattr("__doc__", "High-performance Rust core for Pravah file and data processing.")?;

    Ok(())
}