use thiserror::Error;
use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3::{PyErr, IntoPy};

/// Custom error types for the `sanchay_core` Rust crate.
///
/// This enum consolidates all potential failures that can occur within the
/// Rust core engine, providing a unified and consistent error handling mechanism.
#[derive(Debug, Error)]
pub enum Error {
    /// An I/O error occurred (e.g., file not found, permission denied, disk full).
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// A database error occurred (e.g., SQL syntax error, connection issues, constraint violation).
    #[error("Database error: {0}")]
    Database(#[from] rusqlite::Error),

    /// An error occurred during data serialization or deserialization (e.g., JSON parsing failed).
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// An error occurred during core file or data processing logic (e.g., invalid input, hash mismatch).
    #[error("Processing error: {0}")]
    ProcessingError(String),

    /// An error originating from the Python interpreter when calling back into Python
    /// or capturing a Python exception within Rust.
    #[error("Python error: {0}")]
    Python(#[from] PyErr),
}

/// A convenience type alias for results returned by functions in the `sanchay_core`.
///
/// This simplifies error propagation using the `?` operator.
pub type Result<T> = std::result::Result<T, Error>;

/// Implements `IntoPy<PyErr>` for the custom `Error` enum.
///
/// This conversion allows `sanchay_core::Error` instances to be transparently
/// converted into Python exceptions when returned from functions exposed via PyO3.
/// It maps Rust error types to appropriate Python exception types for better
/// integration and clarity in Python traceback.
impl IntoPy<PyErr> for Error {
    fn into_py(self, py: pyo3::Python) -> PyErr {
        match self {
            Error::Io(err) => PyIOError::new_err(format!("I/O Error: {}", err)).into_py(py),
            Error::Database(err) => PyRuntimeError::new_err(format!("Database Error: {}", err)).into_py(py),
            Error::Serialization(err) => PyValueError::new_err(format!("Serialization Error: {}", err)).into_py(py),
            Error::ProcessingError(msg) => PyRuntimeError::new_err(format!("Processing Error: {}", msg)).into_py(py),
            // If the error is already a PyErr, just return it as is.
            Error::Python(err) => err,
        }
    }
}