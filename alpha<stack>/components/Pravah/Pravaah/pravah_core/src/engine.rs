use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use tokio::fs::{File, OpenOptions};
use tokio::io::{self, AsyncReadExt, AsyncWriteExt};
use tokio::sync::Semaphore;
use walkdir::WalkDir;
use futures::stream::{FuturesOrdered, StreamExt};
use rayon::prelude::*; // Used for potential CPU-bound operations within file processing

use crate::models::{JobParameters, ProcessingResult, ProcessingAction};
use crate::error::PravahError;

/// This trait defines the interface for different file processing strategies.
/// The `#[async_trait]` macro allows us to define async methods in traits.
#[async_trait::async_trait]
trait FileProcessor: Send + Sync {
    /// Processes a single file from `input_path` and writes results to `output_path`.
    async fn process_file(&self, input_path: &Path, output_path: &Path) -> Result<(), PravahError>;
}

/// A simple processor that copies the content of an input file to an output file.
struct CopyFileProcessor;

#[async_trait::async_trait]
impl FileProcessor for CopyFileProcessor {
    async fn process_file(&self, input_path: &Path, output_path: &Path) -> Result<(), PravahError> {
        log::debug!("Processing file (copy): {:?}", input_path);
        let mut input_file = File::open(input_path).await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to open input file {:?}: {}", input_path, e)))
        })?;

        // Ensure the parent directory for the output file exists
        let parent_dir = output_path.parent().ok_or_else(|| {
            PravahError::PathError(format!("Output path {:?} has no parent directory", output_path))
        })?;
        tokio::fs::create_dir_all(parent_dir).await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to create output directory {:?}: {}", parent_dir, e)))
        })?;

        let mut output_file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true) // Overwrite if exists
            .open(output_path)
            .await
            .map_err(|e| {
                PravahError::IoError(io::Error::new(e.kind(), format!("Failed to open output file {:?}: {}", output_path, e)))
            })?;

        io::copy(&mut input_file, &mut output_file).await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to copy data from {:?} to {:?}: {}", input_path, output_path, e)))
        })?;
        log::info!("Successfully copied file from {:?} to {:?}", input_path, output_path);
        Ok(())
    }
}

/// A processor that extracts the first N lines from an input file.
struct ExtractFirstLinesProcessor {
    num_lines: usize,
}

#[async_trait::async_trait]
impl FileProcessor for ExtractFirstLinesProcessor {
    async fn process_file(&self, input_path: &Path, output_path: &Path) -> Result<(), PravahError> {
        log::debug!("Processing file (extract first {} lines): {:?}", self.num_lines, input_path);
        let file = File::open(input_path).await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to open input file {:?}: {}", input_path, e)))
        })?;
        
        // Use BufReader::lines() for line-by-line reading in async context
        let mut lines = tokio::io::BufReader::new(file).lines();
        let mut output_content_lines: Vec<String> = Vec::new();

        for _ in 0..self.num_lines {
            if let Some(line_res) = lines.next_line().await {
                match line_res {
                    Ok(Some(line)) => output_content_lines.push(line),
                    Ok(None) => break, // End of file
                    Err(e) => return Err(PravahError::IoError(io::Error::new(e.kind(), format!("Error reading line from {:?}: {}", input_path, e)))),
                }
            } else {
                break; // No more lines or error (handled by inner match)
            }
        }

        // Potential CPU-bound work can be parallelized here using Rayon, e.g.:
        // let processed_lines: Vec<String> = output_content_lines.par_iter().map(|line| {
        //     // Perform some heavy computation on each line, e.g., parsing, transformation
        //     line.to_uppercase()
        // }).collect();
        // let final_output = processed_lines.join("\n") + "\n";
        
        let final_output = output_content_lines.join("\n") + "\n";

        // Ensure the parent directory for the output file exists
        let parent_dir = output_path.parent().ok_or_else(|| {
            PravahError::PathError(format!("Output path {:?} has no parent directory", output_path))
        })?;
        tokio::fs::create_dir_all(parent_dir).await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to create output directory {:?}: {}", parent_dir, e)))
        })?;

        let mut output_file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .open(output_path)
            .await
            .map_err(|e| {
                PravahError::IoError(io::Error::new(e.kind(), format!("Failed to open output file {:?}: {}", output_path, e)))
            })?;

        output_file.write_all(final_output.as_bytes()).await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to write to output file {:?}: {}", output_path, e)))
        })?;
        output_file.flush().await.map_err(|e| {
            PravahError::IoError(io::Error::new(e.kind(), format!("Failed to flush output file {:?}: {}", output_path, e)))
        })?;

        log::info!("Successfully extracted first {} lines from {:?} to {:?}", self.num_lines, input_path, output_path);
        Ok(())
    }
}

/// The main asynchronous function to process data based on job parameters.
/// This function coordinates directory traversal, file filtering, and parallel processing.
pub async fn process_data(params: JobParameters) -> ProcessingResult {
    log::info!("Starting data processing job: {}", params.job_id);
    log::debug!("Job parameters: {:?}", params);

    let input_path = PathBuf::from(&params.input_path);
    let output_base_path = PathBuf::from(&params.output_path);

    // Atomic counters for tracking results across concurrent tasks
    let total_files_processed = Arc::new(AtomicUsize::new(0));
    let errors_encountered = Arc::new(AtomicUsize::new(0));

    // Select the appropriate file processor based on the requested action
    let processor: Arc<dyn FileProcessor + Send + Sync> = match params.processing_action {
        ProcessingAction::Copy => Arc::new(CopyFileProcessor),
        ProcessingAction::ExtractFirstLines { num_lines } => Arc::new(ExtractFirstLinesProcessor { num_lines }),
        // Extend with more processing actions here
    };

    // Semaphore to limit the number of concurrently executing file processing tasks
    // This helps prevent resource exhaustion (e.g., too many open file handles).
    // The value can be configured based on system I/O capabilities and anticipated load.
    let max_concurrent_io_tasks = 500; 
    let semaphore = Arc::new(Semaphore::new(max_concurrent_io_tasks));

    // FuturesOrdered ensures that we can collect results from spawned tasks in the order
    // they complete, while still running them concurrently.
    let mut processing_futures = FuturesOrdered::new();

    // Perform directory traversal. This part is synchronous, but `walkdir` is highly optimized.
    // For extremely large directory trees that cause blocking, this could be moved to
    // `tokio::task::spawn_blocking` if necessary.
    for entry_result in WalkDir::new(&input_path).into_iter() {
        let entry = match entry_result {
            Ok(e) => e,
            Err(e) => {
                log::warn!("Error traversing directory entry: {}", e);
                errors_encountered.fetch_add(1, Ordering::Relaxed);
                continue;
            }
        };

        let entry_path = entry.path().to_path_buf();

        if !entry_path.is_file() {
            continue; // Only process files
        }

        // Apply file filters based on the job parameters
        if let Some(ref include_extensions) = params.file_filters.include_extensions {
            if let Some(ext) = entry_path.extension().and_then(|s| s.to_str()) {
                if !include_extensions.contains(&ext.to_string()) {
                    log::debug!("Skipping file {:?} due to include extension filter", entry_path);
                    continue;
                }
            } else {
                // If include_extensions are specified, files without extensions are skipped by default
                log::debug!("Skipping file {:?} (no extension) due to include extension filter active", entry_path);
                continue;
            }
        }
        if let Some(ref exclude_extensions) = params.file_filters.exclude_extensions {
            if let Some(ext) = entry_path.extension().and_then(|s| s.to_str()) {
                if exclude_extensions.contains(&ext.to_string()) {
                    log::debug!("Skipping file {:?} due to exclude extension filter", entry_path);
                    continue;
                }
            }
        }
        // Add more file filters here (e.g., min_size_bytes, max_size_bytes, regex_pattern)

        // Calculate the output path, preserving the relative directory structure from the input_path
        let relative_path = entry_path.strip_prefix(&input_path)
            .map_err(|e| PravahError::PathError(format!("Failed to strip prefix from {:?}: {}", entry_path, e)));
        
        let output_file_path = match relative_path {
            Ok(rel_path) => output_base_path.join(rel_path),
            Err(e) => {
                log::error!("Error determining relative path for {:?}: {}", entry_path, e);
                errors_encountered.fetch_add(1, Ordering::Relaxed);
                continue;
            }
        };

        // Clone Arc's for use in the spawned task
        let current_processor = Arc::clone(&processor);
        let tfp_clone = Arc::clone(&total_files_processed);
        let ee_clone = Arc::clone(&errors_encountered);
        let input_file_path_clone = entry_path.clone();
        let output_file_path_clone = output_file_path.clone();

        // Acquire a permit from the semaphore before spawning the task.
        // This will pause if too many tasks are already running.
        let permit = Arc::clone(&semaphore).acquire_owned().await;

        // Spawn an asynchronous task for each file. This allows non-blocking I/O operations
        // to run concurrently.
        let fut = tokio::spawn(async move {
            let _permit_guard = permit; // The permit is held until this async block completes
            match current_processor.process_file(&input_file_path_clone, &output_file_path_clone).await {
                Ok(_) => {
                    tfp_clone.fetch_add(1, Ordering::Relaxed);
                },
                Err(e) => {
                    ee_clone.fetch_add(1, Ordering::Relaxed);
                    log::error!("Failed to process file {:?}: {}", input_file_path_clone, e);
                }
            }
        });
        processing_futures.push_back(fut);
    }

    // Await all spawned processing tasks. This loop will continue as tasks complete.
    while let Some(result) = processing_futures.next().await {
        // Handle potential panics or task failures from `tokio::spawn` (e.g., if a task itself panics)
        if let Err(join_error) = result {
            log::error!("A file processing task panicked or failed to join: {}", join_error);
            errors_encountered.fetch_add(1, Ordering::Relaxed);
        }
    }

    let final_total = total_files_processed.load(Ordering::Relaxed);
    let final_errors = errors_encountered.load(Ordering::Relaxed);

    log::info!("Data processing job {} finished. Total files processed: {}, Errors encountered: {}", 
               params.job_id, final_total, final_errors);

    ProcessingResult {
        total_files_processed: final_total as u64,
        errors_encountered: final_errors as u64,
    }
}