use std::path::{Path, PathBuf};
use chrono::{DateTime, Utc};

// Assuming `error.rs` defines `pub enum FileError` and is accessible in the crate root.
// This typically means `src/lib.rs` contains `mod error;` and `src/error.rs` defines the enum.
use crate::error::FileError;

/// Attempts to canonicalize a given input path and optionally enforce a base directory constraint.
///
/// This function resolves `.` and `..` components and symlinks to produce an absolute,
/// canonicalized path. It then verifies that this resolved path is contained within
/// the specified `base_dir` if one is provided. This is a critical step for preventing
/// path traversal vulnerabilities, ensuring that user-supplied paths do not access
/// files or directories outside of permitted boundaries.
///
/// # Behavior
/// - If `base_dir` is `Some`, the function ensures the `input_path` (after canonicalization)
///   is strictly a sub-path of the `base_dir`. Both paths are canonicalized for a robust comparison.
/// - If `base_dir` is `None`, the function only performs canonicalization of the `input_path`
///   without enforcing any directory containment. In this case, it is the caller's
///   responsibility to ensure the resolved path is within acceptable operational boundaries.
///
/// # Errors
/// Returns `FileError::PathDoesNotExist` if `input_path` or `base_dir` (if provided)
/// does not exist on the filesystem.
/// Returns `FileError::Io` for other underlying I/O errors encountered during path resolution
/// (e.g., permission denied).
/// Returns `FileError::PathTraversal` if `input_path` attempts to resolve to a location
/// outside of the `base_dir` when a constraint is active.
///
/// # Examples
/// ```no_run
/// use std::path::{Path, PathBuf};
/// // Assuming `FileError` is properly defined and accessible
/// # pub enum FileError { Io(std::io::Error), PathTraversal(String), PathDoesNotExist(String) }
/// # impl From<std::io::Error> for FileError { fn from(err: std::io::Error) -> Self { FileError::Io(err) } }
/// # // Mock canonicalize for example clarity, as it needs real filesystem interaction
/// # fn mock_canonicalize(p: &Path) -> Result<PathBuf, std::io::Error> {
/// #     if p.to_str().unwrap().contains("non_existent") {
/// #         Err(std::io::Error::new(std::io::ErrorKind::NotFound, "not found"))
/// #     } else {
/// #         Ok(PathBuf::from("/mock_root").join(p))
/// #     }
/// # }
/// # // Mock the actual function to use the mock_canonicalize
/// # fn sanitize_and_constrain_path(
/// #    input_path: &str,
/// #    base_dir: Option<&Path>,
/// # ) -> Result<PathBuf, FileError> {
/// #    let path = PathBuf::from(input_path);
/// #    let canonical_path = mock_canonicalize(&path)?;
/// #    if let Some(base) = base_dir {
/// #        let canonical_base = mock_canonicalize(base)?;
/// #        if !canonical_path.starts_with(&canonical_base) {
/// #            return Err(FileError::PathTraversal(format!("'{}' out of '{}'", input_path, base.display())));
/// #        }
/// #    }
/// #    Ok(canonical_path)
/// # }
///
/// // Example 1: Valid path within a base directory
/// let base = PathBuf::from("/data/user_files");
/// let safe_path = sanitize_and_constrain_path(
///     "project_x/docs/report.pdf", Some(&base)
/// ).expect("Should be a valid path");
/// // On a real filesystem, `safe_path` would resolve to `/data/user_files/project_x/docs/report.pdf`
/// println!("Sanitized safe path: {:?}", safe_path);
///
/// // Example 2: Path traversal attempt
/// let traversal_path_result = sanitize_and_constrain_path(
///     "../etc/passwd", Some(&base)
/// );
/// assert!(traversal_path_result.is_err());
/// if let Err(e) = traversal_path_result {
///     assert!(matches!(e, FileError::PathTraversal(_)));
///     println!("Successfully caught path traversal: {}", e);
/// }
///
/// // Example 3: Path does not exist
/// let non_existent_path_result = sanitize_and_constrain_path(
///     "/tmp/non_existent_file.txt", None
/// );
/// assert!(non_existent_path_result.is_err());
/// if let Err(e) = non_existent_path_result {
///     assert!(matches!(e, FileError::PathDoesNotExist(_)));
///     println!("Successfully caught non-existent path: {}", e);
/// }
/// ```
pub fn sanitize_and_constrain_path(
    input_path: &str,
    base_dir: Option<&Path>,
) -> Result<PathBuf, FileError> {
    let path = PathBuf::from(input_path);

    // 1. Resolve the input path to its absolute, canonical form.
    // This resolves `.` and `..` components and symlinks.
    let canonical_path = match path.canonicalize() {
        Ok(p) => p,
        Err(e) => {
            if e.kind() == std::io::ErrorKind::NotFound {
                return Err(FileError::PathDoesNotExist(input_path.to_string()));
            } else {
                return Err(FileError::Io(e));
            }
        }
    };

    // 2. If a base directory is provided, ensure the canonicalized path is within it.
    if let Some(base) = base_dir {
        // Canonicalize the base directory as well to ensure a proper and secure comparison.
        let canonical_base = base.canonicalize().map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                FileError::PathDoesNotExist(base.display().to_string())
            } else {
                FileError::Io(e)
            }
        })?;

        // Check if the canonicalized user path starts with the canonicalized base path.
        // This is the robust way to prevent path traversal for *existing* files.
        if !canonical_path.starts_with(&canonical_base) {
            return Err(FileError::PathTraversal(format!(
                "Path '{}' (resolved to '{}') attempts to access files outside the allowed base directory '{}' (resolved to '{}')",
                input_path,
                canonical_path.display(),
                base.display(),
                canonical_base.display()
            )));
        }
    }

    Ok(canonical_path)
}

/// Generates a current UTC timestamp string in ISO 8601 format.
///
/// This function provides a consistent way to obtain the current time in a standardized
/// format, which is useful for logging, metadata generation, and tracking job execution times.
/// The timestamp includes milliseconds and is suffixed with 'Z' to indicate UTC.
///
/// # Returns
/// A `String` representation of the current UTC timestamp, e.g., "2023-10-27T10:30:45.123Z".
///
/// # Examples
/// ```
/// // Assuming `vegafs_core` is the crate name and `utils` is a module within it.
/// let timestamp = vegafs_core::utils::current_utc_timestamp_iso();
/// println!("Current UTC time: {}", timestamp);
/// // Example output might look like: "2023-10-27T10:30:45.123Z"
/// ```
pub fn current_utc_timestamp_iso() -> String {
    let now: DateTime<Utc> = Utc::now();
    // Format as ISO 8601 with milliseconds and 'Z' for UTC.
    now.to_rfc3339_opts(chrono::SecondsFormat::Millis, true)
}