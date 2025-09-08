use std::path::{Path, PathBuf};
use walkdir::{WalkDir, DirEntry};
use rayon::prelude::*;

use crate::error::{SanchayCoreError, Result};

/// Recursively walks a directory, collecting paths to all files within it.
///
/// This function utilizes `walkdir` for efficient directory traversal and `rayon`
/// for parallel processing of directory entries, ensuring high performance.
/// It filters out directories and only returns paths to regular files.
/// Errors encountered during directory traversal (e.g., permission denied) are
/// logged to stderr and skipped, allowing the process to continue.
///
/// # Arguments
/// * `root_path` - A reference to the starting `Path` for the traversal.
///
/// # Returns
/// A `Result` containing a `Vec<PathBuf>` of all discovered file paths,
/// or a `SanchayCoreError` if the initial `root_path` does not exist or
/// is not a valid directory/file.
///
/// # Examples
/// ```no_run
/// use std::path::PathBuf;
/// use sanchay_core::error::Result; // Assume Result is defined in crate::error
/// use sanchay_core::walker;
///
/// // Create a temporary directory structure for testing
/// # fn create_test_dir() -> PathBuf {
/// #    use std::fs;
/// #    let tmp_dir = PathBuf::from("target/doc_test_walk_dir");
/// #    if tmp_dir.exists() { let _ = fs::remove_dir_all(&tmp_dir); }
/// #    fs::create_dir_all(&tmp_dir).unwrap();
/// #    fs::write(tmp_dir.join("file1.txt"), "content").unwrap();
/// #    fs::create_dir_all(tmp_dir.join("sub_dir")).unwrap();
/// #    fs::write(tmp_dir.join("sub_dir/file2.log"), "log content").unwrap();
/// #    tmp_dir
/// # }
/// #
/// # let test_dir = create_test_dir();
/// #
/// let file_paths = walker::walk_directory_parallel(&test_dir).unwrap();
/// assert_eq!(file_paths.len(), 2);
/// assert!(file_paths.iter().any(|p| p.ends_with("file1.txt")));
/// assert!(file_paths.iter().any(|p| p.ends_with("file2.log")));
/// # let _ = std::fs::remove_dir_all(&test_dir);
/// ```
pub fn walk_directory_parallel(root_path: &Path) -> Result<Vec<PathBuf>> {
    if !root_path.exists() {
        return Err(SanchayCoreError::IOError(
            std::io::Error::new(std::io::ErrorKind::NotFound, "Root path does not exist.")
        ));
    }

    if root_path.is_file() {
        // If the path points to a single file, just return that file's path.
        // This handles cases where the user might specify a file directly instead of a directory.
        return Ok(vec![root_path.to_path_buf()]);
    }

    // Initialize WalkDir for the given path.
    // into_iter() consumes it and returns a sequential iterator over DirEntry or Error.
    // par_bridge() bridges the sequential iterator to a parallel one for Rayon.
    let files: Vec<PathBuf> = WalkDir::new(root_path)
        .into_iter()
        .par_bridge() // Converts `Iterator<Item = Result<DirEntry>>` into `ParallelIterator<Item = Result<DirEntry>>`
        .filter_map(|entry_result| {
            match entry_result {
                Ok(entry) => {
                    // Check if the entry is a file. Symlinks are followed by default and their target type is checked.
                    if entry.file_type().is_file() {
                        Some(entry.into_path())
                    } else {
                        // Skip directories, symlinks to directories, or other special files
                        None
                    }
                }
                Err(err) => {
                    // Log errors encountered during traversal (e.g., permission denied)
                    // and continue with other entries. A more robust solution might
                    // collect these errors or report them back to the caller.
                    eprintln!("Error traversing path {:?}: {}", err.path().unwrap_or_default(), err);
                    None // Skip this entry
                }
            }
        })
        .collect(); // Collect all processed file paths into a Vec

    Ok(files)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;
    use tempfile::tempdir; // A crate for creating temporary directories

    #[test]
    fn test_walk_empty_directory() {
        let tmp_dir = tempdir().unwrap();
        let files = walk_directory_parallel(tmp_dir.path()).unwrap();
        assert!(files.is_empty());
    }

    #[test]
    fn test_walk_directory_with_files() {
        let tmp_dir = tempdir().unwrap();
        fs::write(tmp_dir.path().join("file1.txt"), "content1").unwrap();
        fs::write(tmp_dir.path().join("file2.txt"), "content2").unwrap();

        let files = walk_directory_parallel(tmp_dir.path()).unwrap();
        assert_eq!(files.len(), 2);
        assert!(files.iter().any(|p| p.file_name().unwrap() == "file1.txt"));
        assert!(files.iter().any(|p| p.file_name().unwrap() == "file2.txt"));
    }

    #[test]
    fn test_walk_directory_with_subdirectories() {
        let tmp_dir = tempdir().unwrap();
        fs::write(tmp_dir.path().join("file1.txt"), "content1").unwrap();
        let sub_dir = tmp_dir.path().join("sub_dir");
        fs::create_dir(&sub_dir).unwrap();
        fs::write(sub_dir.join("file2.txt"), "content2").unwrap();
        let sub_sub_dir = sub_dir.join("sub_sub_dir");
        fs::create_dir(&sub_sub_dir).unwrap();
        fs::write(sub_sub_dir.join("file3.txt"), "content3").unwrap();

        let files = walk_directory_parallel(tmp_dir.path()).unwrap();
        assert_eq!(files.len(), 3);
        assert!(files.iter().any(|p| p.file_name().unwrap() == "file1.txt"));
        assert!(files.iter().any(|p| p.file_name().unwrap() == "file2.txt"));
        assert!(files.iter().any(|p| p.file_name().unwrap() == "file3.txt"));
    }

    #[test]
    fn test_walk_non_existent_path() {
        let non_existent_path = PathBuf::from("non_existent_dir_12345");
        let err = walk_directory_parallel(&non_existent_path).unwrap_err();
        assert!(matches!(err, SanchayCoreError::IOError(ref io_err) if io_err.kind() == std::io::ErrorKind::NotFound));
    }

    #[test]
    fn test_walk_single_file() {
        let tmp_dir = tempdir().unwrap();
        let file_path = tmp_dir.path().join("single_file.txt");
        fs::write(&file_path, "single content").unwrap();

        let files = walk_directory_parallel(&file_path).unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0], file_path);
    }

    #[test]
    fn test_permission_denied_directory() {
        let tmp_dir = tempdir().unwrap();
        let protected_dir = tmp_dir.path().join("protected_dir");
        fs::create_dir(&protected_dir).unwrap();
        fs::write(protected_dir.join("protected_file.txt"), "content").unwrap();

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&protected_dir).unwrap().permissions();
            perms.set_mode(0o000); // Remove all permissions
            fs::set_permissions(&protected_dir, perms).unwrap();
        }

        let files = walk_directory_parallel(tmp_dir.path()).unwrap();

        #[cfg(unix)]
        {
            // Restore permissions for cleanup
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&protected_dir).unwrap().permissions();
            perms.set_mode(0o755);
            fs::set_permissions(&protected_dir, perms).unwrap();
        }

        // The file inside `protected_dir` should not be included if permissions prevented access.
        // Other files in `tmp_dir` (if any were created for the test) would still be found.
        assert_eq!(files.len(), 0, "No files should be collected from unreadable directory");
    }
}