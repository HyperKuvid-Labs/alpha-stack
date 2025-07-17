```rust
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// --- Enums ---

/// Represents the supported image formats for processing.
/// Exposed to Python to allow type-safe specification of image formats.
#[pyclass]
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ImageFormat {
    /// JPEG image format.
    #[pyo3(name = "JPEG")]
    Jpeg,
    /// PNG image format.
    #[pyo3(name = "PNG")]
    Png,
    /// WebP image format.
    #[pyo3(name = "WEBP")]
    Webp,
}

#[pymethods]
impl ImageFormat {
    /// Creates a new JPEG ImageFormat instance.
    #[new]
    fn new_jpeg() -> Self {
        ImageFormat::Jpeg
    }
    /// Creates a new PNG ImageFormat instance.
    #[new]
    fn new_png() -> Self {
        ImageFormat::Png
    }
    /// Creates a new WebP ImageFormat instance.
    #[new]
    fn new_webp() -> Self {
        ImageFormat::Webp
    }

    /// Provides a string representation for the ImageFormat, typically its uppercase name.
    fn __str__(&self) -> String {
        format!("{:?}", self).to_uppercase()
    }
    /// Provides a detailed string representation for Python's repr().
    fn __repr__(&self) -> String {
        self.__str__()
    }
}

/// Defines the type of processing to be performed on files.
/// This enum is tagged for serialization/deserialization, meaning its JSON/Python dictionary
/// representation will include a "type" field to distinguish variants, and a "data" field
/// for variants that carry additional information.
/// Exposed to Python to allow direct construction and specification of processing types.
#[pyclass]
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "type", content = "data")]
pub enum ProcessingType {
    /// Extracts header rows from supported file types (e.g., CSV).
    ExtractHeaders,
    /// Compresses the target file.
    CompressFile,
    /// Resizes an image to specified dimensions and converts to a given format.
    ResizeImage {
        #[pyo3(get, set)]
        width: u32,
        #[pyo3(get, set)]
        height: u32,
        #[pyo3(get, set)]
        format: ImageFormat,
    },
    /// Executes a custom script for processing.
    CustomScript {
        #[pyo3(get, set)]
        script_path: String,
        #[pyo3(get, set)]
        args: Vec<String>,
    },
}

#[pymethods]
impl ProcessingType {
    /// Creates a new `ExtractHeaders` processing type instance.
    #[new]
    fn new_extract_headers() -> Self {
        ProcessingType::ExtractHeaders
    }

    /// Creates a new `CompressFile` processing type instance.
    #[new]
    fn new_compress_file() -> Self {
        ProcessingType::CompressFile
    }

    /// Creates a new `ResizeImage` processing type instance.
    ///
    /// # Arguments
    /// * `width` - The target width for the resized image.
    /// * `height` - The target height for the resized image.
    /// * `format` - The target image format (e.g., JPEG, PNG).
    #[new]
    #[pyo3(signature = (width, height, format))]
    fn new_resize_image(width: u32, height: u32, format: ImageFormat) -> Self {
        ProcessingType::ResizeImage { width, height, format }
    }

    /// Creates a new `CustomScript` processing type instance.
    ///
    /// # Arguments
    /// * `script_path` - The path to the custom script to execute.
    /// * `args` - A list of arguments to pass to the custom script.
    #[new]
    #[pyo3(signature = (script_path, args))]
    fn new_custom_script(script_path: String, args: Vec<String>) -> Self {
        ProcessingType::CustomScript { script_path, args }
    }

    /// Provides a detailed string representation for Python's repr().
    fn __repr__(&self) -> String {
        format!("{:?}", self)
    }
}

/// Represents the current status of a processing job or a single file's processing outcome.
/// Exposed to Python for clear status tracking.
#[pyclass]
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    /// The job/file is awaiting processing.
    #[pyo3(name = "PENDING")]
    Pending,
    /// The job/file is currently being processed.
    #[pyo3(name = "RUNNING")]
    Running,
    /// The job/file has completed successfully.
    #[pyo3(name = "COMPLETED")]
    Completed,
    /// The job/file processing failed.
    #[pyo3(name = "FAILED")]
    Failed,
    /// The job/file processing was cancelled.
    #[pyo3(name = "CANCELLED")]
    Cancelled,
}

#[pymethods]
impl JobStatus {
    /// Creates a new `Pending` job status.
    #[new]
    fn new_pending() -> Self {
        JobStatus::Pending
    }
    /// Creates a new `Running` job status.
    #[new]
    fn new_running() -> Self {
        JobStatus::Running
    }
    /// Creates a new `Completed` job status.
    #[new]
    fn new_completed() -> Self {
        JobStatus::Completed
    }
    /// Creates a new `Failed` job status.
    #[new]
    fn new_failed() -> Self {
        JobStatus::Failed
    }
    /// Creates a new `Cancelled` job status.
    #[new]
    fn new_cancelled() -> Self {
        JobStatus::Cancelled
    }

    /// Provides a string representation for the JobStatus, typically its uppercase name.
    fn __str__(&self) -> String {
        format!("{:?}", self).to_uppercase()
    }
    /// Provides a detailed string representation for Python's repr().
    fn __repr__(&self) -> String {
        self.__str__()
    }
}

// --- Structs ---

/// Represents the input parameters for a new processing job, received from the Python layer.
/// This struct is a PyO3 class, making it directly usable and constructible from Python.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobInput {
    /// A unique identifier for the job, typically generated by the Python orchestrator.
    #[pyo3(get)]
    pub job_id: String,
    /// The path to the source directory or file to be processed.
    #[pyo3(get)]
    pub source_path: String,
    /// An optional path where processed files or results should be stored.
    /// If None, in-place processing or default storage might be implied.
    #[pyo3(get)]
    pub output_path: Option<String>,
    /// A list of glob patterns (e.g., "*.csv", "*.log") to filter files for processing.
    #[pyo3(get)]
    pub file_patterns: Vec<String>,
    /// The specific type of processing to apply to the files.
    #[pyo3(get)]
    pub processing_type: ProcessingType,
    /// An optional maximum number of concurrent file processing tasks.
    /// If None, the engine will determine an optimal concurrency level.
    #[pyo3(get)]
    pub max_concurrency: Option<usize>,
}

#[pymethods]
impl JobInput {
    /// Creates a new `JobInput` instance.
    ///
    /// # Arguments
    /// * `job_id` - Unique identifier for the job.
    /// * `source_path` - Path to the source data.
    /// * `file_patterns` - List of file patterns to include.
    /// * `processing_type` - The type of processing to perform.
    /// * `output_path` - Optional path for output.
    /// * `max_concurrency` - Optional maximum concurrency limit.
    #[new]
    #[pyo3(signature = (job_id, source_path, file_patterns, processing_type, output_path = None, max_concurrency = None))]
    fn new(
        job_id: String,
        source_path: String,
        file_patterns: Vec<String>,
        processing_type: ProcessingType,
        output_path: Option<String>,
        max_concurrency: Option<usize>,
    ) -> Self {
        JobInput {
            job_id,
            source_path,
            output_path,
            file_patterns,
            processing_type,
            max_concurrency,
        }
    }

    /// Provides a detailed string representation for Python's repr().
    fn __repr__(&self) -> String {
        format!(
            "JobInput(job_id='{}', source_path='{}', file_patterns={:?}, processing_type={:?}, max_concurrency={:?})",
            self.job_id, self.source_path, self.file_patterns, self.processing_type, self.max_concurrency
        )
    }
}

/// Represents internal metadata about a file, typically gathered during directory traversal.
/// This struct is primarily for internal Rust engine use and not directly exposed to Python
/// via PyO3, but it derives `Serialize` and `Deserialize` for potential internal state
/// management or structured logging.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileMetadata {
    /// The full path to the file.
    pub path: String,
    /// The size of the file in bytes.
    pub size: u64,
    /// The last modification timestamp of the file (Unix epoch seconds).
    pub last_modified_unix: u64,
    /// Indicates if the path refers to a directory.
    pub is_dir: bool,
}

/// Represents the outcome of processing a single file, sent back from the Rust engine to Python.
/// This struct is a PyO3 class, making it directly usable and inspectable from Python.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingResult {
    /// The unique identifier of the job this result belongs to.
    #[pyo3(get)]
    pub job_id: String,
    /// The full path to the file that was processed.
    #[pyo3(get)]
    pub file_path: String,
    /// The status of the file's processing (e.g., COMPLETED, FAILED).
    #[pyo3(get)]
    pub status: JobStatus,
    /// An optional message providing more details about the processing outcome (e.g., error message).
    #[pyo3(get)]
    pub message: Option<String>,
    /// An optional path to the newly created or modified file, if applicable.
    #[pyo3(get)]
    pub output_path: Option<String>,
    /// The time taken to process this specific file, in milliseconds.
    #[pyo3(get)]
    pub processing_time_ms: u64,
    /// The total bytes processed for this file (e.g., bytes read, bytes written).
    #[pyo3(get)]
    pub bytes_processed: u64,
    /// A flexible dictionary for any custom metrics or key-value data specific to the processing type.
    #[pyo3(get)]
    pub custom_metrics: Option<HashMap<String, String>>,
}

#[pymethods]
impl ProcessingResult {
    /// Creates a new `ProcessingResult` instance.
    ///
    /// # Arguments
    /// * `job_id` - The ID of the job this result belongs to.
    /// * `file_path` - The path of the file that was processed.
    /// * `status` - The processing status for this file.
    /// * `message` - Optional message.
    /// * `output_path` - Optional path to the output file.
    /// * `processing_time_ms` - Time taken for processing in milliseconds.
    /// * `bytes_processed` - Total bytes processed.
    /// * `custom_metrics` - Optional dictionary of custom metrics.
    #[new]
    #[pyo3(signature = (job_id, file_path, status, message = None, output_path = None, processing_time_ms = 0, bytes_processed = 0, custom_metrics = None))]
    fn new(
        job_id: String,
        file_path: String,
        status: JobStatus,
        message: Option<String>,
        output_path: Option<String>,
        processing_time_ms: u64,
        bytes_processed: u64,
        custom_metrics: Option<HashMap<String, String>>,
    ) -> Self {
        ProcessingResult {
            job_id,
            file_path,
            status,
            message,
            output_path,
            processing_time_ms,
            bytes_processed,
            custom_metrics,
        }
    }

    /// Provides a detailed string representation for Python's repr().
    fn __repr__(&self) -> String {
        format!(
            "ProcessingResult(job_id='{}', file_path='{}', status={:?}, time={}ms, bytes={})",
            self.job_id, self.file_path, self.status, self.processing_time_ms, self.bytes_processed
        )
    }
}
```