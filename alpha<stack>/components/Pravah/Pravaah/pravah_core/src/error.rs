use pyo3::exceptions::{PyFileNotFoundError, PyIOError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use std::path::PathBuf;
use thiserror::Error;

/// Custom Error type for the Pravah core engine.
///
/// This enum centralizes all possible error conditions that can occur within the
/// Rust core, providing detailed information about the failure.
#[derive(Debug, Error)]
pub enum PravahError {
    /// An I/O error occurred, typically from file system operations.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// A specified file or directory was not found.
    #[error("File not found: {}", .0.display())]
    FileNotFound(PathBuf),

    /// An error occurred during the core processing of a file or data.
    #[error("Processing error for {}: {}", .path.as_ref().map_or("data".to_string(), |p| p.display().to_string()), .message)]
    Processing {
        /// The path to the file being processed, if applicable.
        path: Option<PathBuf>,
        /// A descriptive message about the processing error.
        message: String,
    },

    /// An error related to invalid or missing configuration.
    #[error("Configuration error: {0}")]
    Configuration(String),

    /// An unsupported operation was attempted.
    #[error("Unsupported operation: {0}")]
    Unsupported(String),

    /// An internal error occurred within the Pravah core engine.
    /// This typically indicates an unrecoverable or unexpected state.
    #[error("Internal Pravah error: {0}")]
    Internal(String),

    /// A catch-all for any other unexpected or unclassified errors.
    #[error("An unknown error occurred: {0}")]
    Unknown(String),
}

/// A specialized `Result` type for Pravah operations.
///
/// This type simplifies error handling within the Pravah core, making it
/// easier to propagate and manage `PravahError` instances.
pub type PravahResult<T> = Result<T, PravahError>;

/// Implements conversion from `PravahError` to PyO3's `PyErr`.
///
/// This allows Rust functions that return `PravahResult` to be exposed to Python
/// via PyO3, and their errors will automatically be converted into appropriate
/// Python exceptions, making error handling seamless on the Python side.
impl From<PravahError> for PyErr {
    fn from(err: PravahError) -> PyErr {
        match err {
            PravahError::Io(e) => PyIOError::new_err(e.to_string()),
            PravahError::FileNotFound(path) => {
                PyFileNotFoundError::new_err(format!("File not found: {}", path.display()))
            }
            PravahError::Processing { path, message } => {
                let msg = if let Some(p) = path {
                    format!("Processing error for '{}': {}", p.display(), message)
                } else {
                    format!("Processing error: {}", message)
                };
                PyValueError::new_err(msg)
            }
            PravahError::Configuration(msg) => PyValueError::new_err(format!("Configuration error: {}", msg)),
            PravahError::Unsupported(msg) => PyRuntimeError::new_err(format!("Unsupported operation: {}", msg)),
            PravahError::Internal(msg) => PyRuntimeError::new_err(format!("Internal Pravah error: {}", msg)),
            PravahError::Unknown(msg) => PyRuntimeError::new_err(format!("An unknown error occurred in Pravah: {}", msg)),
        }
    }
}