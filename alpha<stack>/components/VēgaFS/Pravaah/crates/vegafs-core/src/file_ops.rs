use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    time::SystemTime,
};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tokio::fs::{self, File};
use tokio::io::AsyncReadExt;
use walkdir::WalkDir;
use rayon::prelude::*;

/// Custom error types for file operations within the VēgaFS core.
#[derive(thiserror::Error, Debug)]
pub enum VegaFsCoreError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Path '{0}' is not valid UTF-8")]
    InvalidUtf8Path(String),
    #[error("Failed to calculate hash: {0}")]
    HashError(String),
    #[error("Failed to parse timestamp: {0}")]
    TimestampParseError(String),
    #[error("Walkdir error: {0}")]
    WalkDir(#[from] walkdir::Error),
    #[error("Failed to acquire metadata for path '{0}'")]
    MetadataError(PathBuf),
    #[error("Failed to get file name from path '{0}'")]
    FileNameError(PathBuf),
    #[error("Path is not a directory: '{0}'")]
    NotADirectory(PathBuf),
}

/// A specialized `Result` type for `VegaFsCoreError`.
pub type Result<T> = std::result::Result<T, VegaFsCoreError>;

/// Represents the type of a file system entry.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum FileType {
    File,
    Directory,
    Symlink,
    Other,
}

impl From<&std::fs::Metadata> for FileType {
    fn from(metadata: &std::fs::Metadata) -> Self {
        if metadata.is_file() {
            FileType::File
        } else if metadata.is_dir() {
            FileType::Directory
        } else if metadata.is_symlink() {
            FileType::Symlink
        } else {
            FileType::Other
        }
    }
}

/// Contains comprehensive metadata for a file system entry.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileMetadata {
    pub path: PathBuf,
    pub name: String,
    pub size: u64,
    pub is_dir: bool,
    pub is_file: bool,
    pub is_symlink: bool,
    pub file_type: FileType,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modified_at: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub accessed_at: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sha256_hash: Option<String>,
}

/// Converts `SystemTime` to `chrono::DateTime<Utc>`.
fn system_time_to_utc_datetime(st: SystemTime) -> Result<DateTime<Utc>> {
    Ok(DateTime::<Utc>::from(st))
}

/// Retrieves basic metadata for a single file or directory asynchronously.
///
/// # Arguments
/// * `path` - A reference to the path of the file or directory.
///
/// # Returns
/// A `Result` containing `FileMetadata` if successful, or `VegaFsCoreError` otherwise.
pub async fn get_single_file_metadata(path: &Path) -> Result<FileMetadata> {
    let metadata = fs::metadata(path)
        .await
        .map_err(|_| VegaFsCoreError::MetadataError(path.to_path_buf()))?;

    let name = path
        .file_name()
        .and_then(|os_str| os_str.to_str())
        .map(|s| s.to_string())
        .ok_or_else(|| VegaFsCoreError::FileNameError(path.to_path_buf()))?;

    Ok(FileMetadata {
        path: path.to_path_buf(),
        name,
        size: metadata.len(),
        is_dir: metadata.is_dir(),
        is_file: metadata.is_file(),
        is_symlink: metadata.is_symlink(),
        file_type: FileType::from(&metadata),
        modified_at: metadata
            .modified()
            .ok()
            .and_then(|st| system_time_to_utc_datetime(st).ok()),
        accessed_at: metadata
            .accessed()
            .ok()
            .and_then(|st| system_time_to_utc_datetime(st).ok()),
        created_at: metadata
            .created()
            .ok()
            .and_then(|st| system_time_to_utc_datetime(st).ok()),
        sha256_hash: None, // Hashing is a separate, potentially heavier operation
    })
}

/// Calculates the SHA256 hash of a file's content asynchronously.
///
/// # Arguments
/// * `path` - A reference to the path of the file.
///
/// # Returns
/// A `Result` containing the hexadecimal string representation of the SHA256 hash,
/// or `VegaFsCoreError` if the file cannot be opened or read.
pub async fn calculate_sha256_for_file(path: &Path) -> Result<String> {
    let mut file = File::open(path).await?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0; 8192]; // Read in 8KB chunks

    loop {
        let bytes_read = file.read(&mut buffer).await?;
        if bytes_read == 0 {
            break;
        }
        hasher.update(&buffer[..bytes_read]);
    }

    Ok(format!("{:x}", hasher.finalize()))
}

/// A summary of a directory's contents.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DirectorySummary {
    pub root_path: PathBuf,
    pub total_files: u64,
    pub total_directories: u64,
    pub total_size: u64, // Sum of file sizes
    pub file_type_counts: HashMap<String, u64>, // e.g., "txt": 10, "jpg": 5
    pub largest_files: Vec<FileMetadata>, // Top N largest files
    pub smallest_files: Vec<FileMetadata>, // Top N smallest files (excluding 0-byte files)
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub errors: Vec<String>, // Errors encountered during traversal
}

/// Internal struct for accumulating summary data in parallel.
#[derive(Default)]
struct SummaryAccumulator {
    total_files: u64,
    total_directories: u64,
    total_size: u64,
    file_type_counts: HashMap<String, u64>,
    file_metadatas: Vec<FileMetadata>,
    errors: Vec<String>,
}

/// Traverses a directory and collects a detailed summary of its contents.
/// This function utilizes `walkdir` for efficient traversal (run on a blocking thread)
/// and `rayon` for parallel processing of file metadata. It does not perform content hashing.
///
/// # Arguments
/// * `path` - A reference to the root path of the directory to summarize.
/// * `max_largest_smallest` - The maximum number of largest and smallest files to return.
///
/// # Returns
/// A `Result` containing `DirectorySummary` if successful, or `VegaFsCoreError` otherwise.
pub async fn summarize_directory(
    path: &Path,
    max_largest_smallest: usize,
) -> Result<DirectorySummary> {
    if !path.is_dir() {
        return Err(VegaFsCoreError::NotADirectory(path.to_path_buf()));
    }

    let root_path_clone = path.to_path_buf();

    // Use spawn_blocking because walkdir is synchronous and blocks the async runtime.
    // Collect all directory entries first.
    let dir_entries = tokio::task::spawn_blocking(move || {
        WalkDir::new(&root_path_clone)
            .into_iter()
            .collect::<Vec<_>>()
    })
    .await
    .map_err(|e| VegaFsCoreError::WalkDir(walkdir::Error::new(std::io::ErrorKind::Other, e)))?;

    let final_accumulator = dir_entries
        .par_iter() // Process entries in parallel using Rayon
        .fold(
            SummaryAccumulator::default,
            |mut acc, entry_result| {
                match entry_result {
                    Ok(entry) => {
                        let path_buf = entry.path().to_path_buf();
                        match entry.metadata() {
                            Ok(metadata) => {
                                let name = path_buf
                                    .file_name()
                                    .and_then(|os_str| os_str.to_str())
                                    .map(|s| s.to_string());

                                if name.is_none() {
                                    acc.errors.push(format!("Could not get UTF-8 name for {:?}", path_buf));
                                    return acc;
                                }
                                let name = name.unwrap(); // Safe to unwrap after None check

                                if metadata.is_dir() {
                                    acc.total_directories += 1;
                                } else if metadata.is_file() {
                                    acc.total_files += 1;
                                    acc.total_size += metadata.len();

                                    let extension = path_buf
                                        .extension()
                                        .and_then(|os_str| os_str.to_str())
                                        .map(|s| s.to_string());

                                    if let Some(ext) = extension {
                                        *acc.file_type_counts.entry(ext).or_insert(0) += 1;
                                    } else {
                                        *acc.file_type_counts.entry("no_extension".to_string()).or_insert(0) += 1;
                                    }

                                    // Collect basic file metadata for largest/smallest sorting
                                    acc.file_metadatas.push(FileMetadata {
                                        path: path_buf.clone(),
                                        name,
                                        size: metadata.len(),
                                        is_dir: metadata.is_dir(),
                                        is_file: metadata.is_file(),
                                        is_symlink: metadata.is_symlink(),
                                        file_type: FileType::from(&metadata),
                                        modified_at: None, // Not retrieving full timestamps/hashes for performance in summary
                                        accessed_at: None,
                                        created_at: None,
                                        sha256_hash: None,
                                    });
                                }
                            }
                            Err(e) => {
                                acc.errors.push(format!("Failed to get metadata for {:?}: {}", path_buf, e));
                            }
                        }
                    }
                    Err(e) => {
                        acc.errors.push(format!("Walkdir error: {}", e));
                    }
                }
                acc
            },
        )
        .reduce(
            SummaryAccumulator::default,
            |mut acc1, acc2| {
                acc1.total_files += acc2.total_files;
                acc1.total_directories += acc2.total_directories;
                acc1.total_size += acc2.total_size;
                for (k, v) in acc2.file_type_counts {
                    *acc1.file_type_counts.entry(k).or_insert(0) += v;
                }
                acc1.file_metadatas.extend(acc2.file_metadatas);
                acc1.errors.extend(acc2.errors);
                acc1
            },
        );

    // Sort collected file metadatas to find largest and smallest
    let mut file_metadatas = final_accumulator.file_metadatas;
    file_metadatas.sort_by_key(|f| f.size);

    let largest_files = file_metadatas
        .iter()
        .rev() // Largest first
        .take(max_largest_smallest)
        .cloned()
        .collect();

    // Smallest files should exclude directories and 0-byte files
    let smallest_files = file_metadatas
        .iter()
        .filter(|f| f.is_file && f.size > 0) // Ensure it's a file and not 0-byte
        .take(max_largest_smallest)
        .cloned()
        .collect();

    Ok(DirectorySummary {
        root_path: path.to_path_buf(),
        total_files: final_accumulator.total_files,
        total_directories: final_accumulator.total_directories,
        total_size: final_accumulator.total_size,
        file_type_counts: final_accumulator.file_type_counts,
        largest_files,
        smallest_files,
        errors: final_accumulator.errors,
    })
}