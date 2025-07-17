use std::path::PathBuf;
use thiserror::Error;

/// Custom error types for the `vegafs-core` library.
///
/// This enum consolidates all potential failures that can occur within the
/// core processing engine, providing a structured and consistent way to
/// handle errors.
#[derive(Error, Debug)]
pub enum CoreError {
    /// An I/O error occurred during file or directory operations.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// An error occurred during directory traversal.
    #[error("Directory traversal error for path '{}': {}", .path.display(), .source)]
    WalkDir {
        path: PathBuf,
        #[source]
        source: walkdir::Error,
    },

    /// An invalid argument or parameter was provided.
    #[error("Validation error: {message}")]
    Validation { message: String },

    /// The specified path does not exist or is not accessible.
    #[error("Path not found or not accessible: '{}'", .path.display())]
    PathNotFound { path: PathBuf },

    /// The specified path is not a directory.
    #[error("Path is not a directory: '{}'", .path.display())]
    NotADirectory { path: PathBuf },

    /// The specified path is not a file.
    #[error("Path is not a file: '{}'", .path.display())]
    NotAFile { path: PathBuf },

    /// An error occurred during serialization or deserialization (e.g., for internal configuration).
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// An unexpected internal error occurred. This should ideally be caught
    /// and converted to more specific errors, but serves as a fallback.
    #[error("Internal error: {message}")]
    Internal { message: String },
}

impl CoreError {
    /// Creates a new `CoreError::Validation` with the given message.
    pub fn validation<S: Into<String>>(message: S) -> Self {
        CoreError::Validation {
            message: message.into(),
        }
    }

    /// Creates a new `CoreError::PathNotFound` for the given path.
    pub fn path_not_found(path: impl Into<PathBuf>) -> Self {
        CoreError::PathNotFound { path: path.into() }
    }

    /// Creates a new `CoreError::NotADirectory` for the given path.
    pub fn not_a_directory(path: impl Into<PathBuf>) -> Self {
        CoreError::NotADirectory { path: path.into() }
    }

    /// Creates a new `CoreError::NotAFile` for the given path.
    pub fn not_a_file(path: impl Into<PathBuf>) -> Self {
        CoreError::NotAFile { path: path.into() }
    }

    /// Creates a new `CoreError::Internal` with the given message.
    pub fn internal<S: Into<String>>(message: S) -> Self {
        CoreError::Internal {
            message: message.into(),
        }
    }
}