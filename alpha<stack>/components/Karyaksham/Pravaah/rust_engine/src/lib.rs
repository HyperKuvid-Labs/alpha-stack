use pyo3::prelude::*;
use pyo3::exceptions::PyException;
use pyo3::create_exception;
use tokio::runtime::Runtime;
use serde::Deserialize;
use anyhow::Context;

// Import internal modules
mod core;
mod utils;

// Use specific items from internal modules
use core::data_processor;
use core::file_handler;
use utils::error::{KaryakshamError, ResultExt}; // Assuming ResultExt for `context()`

// Define a custom Python exception type for errors originating from the Rust engine.
// This allows for more specific error handling on the Python side.
create_exception!(karyaksham_rust_engine, KaryakshamRustEngineError, PyException);

// Implement conversion from our custom Rust error type (`KaryakshamError`) to PyErr.
// This enables automatic error propagation from Rust functions to Python exceptions
// when a `PyResult` is returned.
impl From<KaryakshamError> for PyErr {
    fn from(err: KaryakshamError) -> PyErr {
        KaryakshamRustEngineError::new_err(format!("{}", err))
    }
}

// --- Data Structures for Processing Parameters ---

// These structs define the expected shape of the JSON string passed from Python.
// They use `serde` for efficient deserialization.

#[derive(Debug, Deserialize)]
pub struct CsvProcessingParams {
    pub filters: Option<Vec<FilterCondition>>,
    // Use `Option<Option<Vec<Transformation>>>` to distinguish between missing and empty list
    pub transformations: Option<Option<Vec<Transformation>>>,
    pub output_format: Option<String>,
    pub delimiter: Option<char>, // Specific to CSV
    pub has_header: Option<bool>, // Specific to CSV
    // Add other generic parameters that might apply to multiple file types
    pub columns_to_select: Option<Vec<String>>, // Example: Direct column selection
}

#[derive(Debug, Deserialize)]
#[serde(untagged)] // Allows parsing different JSON types into this enum variant
pub enum FilterValue {
    String(String),
    Number(f64),
    Boolean(bool),
    // Extend with other types as necessary (e.g., Array for 'in' operator)
}

#[derive(Debug, Deserialize)]
pub struct FilterCondition {
    pub column: String,
    pub operator: String, // e.g., "eq", "ne", "gt", "lt", "ge", "le", "contains", "starts_with"
    pub value: FilterValue,
    // Add more fields if filter logic requires, e.g., case_sensitive
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type")] // Discriminate enum variants based on a "type" field in the JSON
pub enum Transformation {
    #[serde(rename = "rename_column")]
    RenameColumn {
        from_column: String,
        to_column: String,
    },
    #[serde(rename = "add_column")]
    AddColumn {
        name: String,
        value: serde_json::Value, // Can be a constant or a simple expression string
        #[serde(default = "default_false")] // Default to false if `from_expression` is missing
        from_expression: bool, // If `value` should be interpreted as an expression
    },
    #[serde(rename = "aggregate")]
    Aggregate {
        group_by_columns: Option<Vec<String>>,
        aggregations: Vec<Aggregation>,
    },
    // Add other transformation types here (e.g., type conversion, join, pivot)
}

// Helper function for `#[serde(default)]`
fn default_false() -> bool { false }

#[derive(Debug, Deserialize)]
pub struct Aggregation {
    pub column: String,
    pub operation: String, // e.g., "sum", "mean", "count", "min", "max", "std"
    pub new_column_name: Option<String>, // Optional new name for the aggregated column
}


// --- Exposed Python Functions ---

/// Processes a CSV file from an S3-compatible object storage, applies transformations,
/// and writes the resulting output to another S3 location.
/// This function is designed to be called by a Python Celery worker to offload
/// computationally intensive file processing.
///
/// # Arguments
/// * `py` - The Python interpreter GIL token. While not directly used for blocking,
///          it's often passed to `pyfunction` for context or potential future use.
/// * `s3_input_path` - The full URI of the input file (e.g., "s3://bucket-name/path/to/input.csv").
/// * `s3_output_path` - The full URI where the processed file should be written.
/// * `processing_params_json` - A JSON string containing the detailed processing configuration
///                              (e.g., filters, column selections, transformations, output format).
///
/// # Returns
/// A `PyResult` containing the `s3_output_path` string on successful completion,
/// or a `PyErr` if any error occurs during the process (e.g., network issues, parsing errors,
/// or processing failures).
#[pyfunction]
fn process_csv_file(
    _py: Python, // Renamed to _py to indicate it's unused in this specific function, per Clippy lint
    s3_input_path: String,
    s3_output_path: String,
    processing_params_json: String,
) -> PyResult<String> {
    // Deserialize the JSON parameters into our Rust struct.
    // This allows Rust to work with strongly-typed configurations.
    let params: CsvProcessingParams = serde_json::from_str(&processing_params_json)
        .context("Failed to deserialize processing parameters JSON. Ensure JSON format matches expected schema.")
        .map_err(KaryakshamError::ParameterError)?; // Convert to our custom error type

    // Create a Tokio runtime for executing asynchronous operations.
    // `block_on` will block the current OS thread until all tasks within the async block
    // complete. This is acceptable for a Celery worker, which is designed to handle
    // long-running tasks.
    let rt = Runtime::new()
        .context("Failed to create Tokio runtime. This is critical for async operations.")
        .map_err(KaryakshamError::RuntimeError)?;

    rt.block_on(async {
        // Load AWS SDK configuration (credentials, region, endpoint).
        // This leverages standard AWS environment variables or config files.
        let config = aws_config::load_from_env().await;
        let s3_client = aws_sdk_s3::Client::new(&config);

        log::info!("Starting CSV processing: Input='{}', Output='{}'", s3_input_path, s3_output_path);
        log::debug!("Processing parameters: {:?}", params);

        // Step 1: Read the input file as a byte stream from S3.
        let input_byte_stream = file_handler::read_stream_from_s3(&s3_client, &s3_input_path)
            .await
            .context(format!("Failed to read data stream from S3 path: '{}'", s3_input_path))
            .map_err(KaryakshamError::IoError)?;

        // Step 2: Process the data stream. This involves parsing the CSV, applying
        // filters and transformations, and potentially converting to a new format.
        let processed_byte_stream = data_processor::process_csv_data(
            input_byte_stream,
            params,
        )
        .await
        .context("Failed during high-performance data processing.")
        .map_err(KaryakshamError::ProcessingError)?;

        // Step 3: Write the processed byte stream back to S3.
        file_handler::write_stream_to_s3(&s3_client, &s3_output_path, processed_byte_stream)
            .await
            .context(format!("Failed to write processed data to S3 path: '{}'", s3_output_path))
            .map_err(KaryakshamError::IoError)?;

        log::info!("Successfully processed CSV: Input='{}', Output='{}'", s3_input_path, s3_output_path);

        Ok(s3_output_path) // Return the output path as confirmation
    })
    .map_err(PyErr::from) // Convert the error from the async block into a PyErr
}

/// A simple test function to verify PyO3 bindings and basic Rust execution.
#[pyfunction]
fn rust_hello_world(name: String) -> PyResult<String> {
    log::info!("rust_hello_world function called with name: {}", name);
    Ok(format!("Hello from Karyaksham Rust Engine, {}!", name))
}

// --- PyO3 Module Definition ---

/// `karyaksham_rust_engine` Python module.
/// This module serves as the primary interface for exposing high-performance
/// data processing functionalities from Rust to the Python application.
#[pymodule]
fn karyaksham_rust_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    // Initialize Rust's `env_logger` for better debugging output when running
    // the Rust code from Python. `is_test(true)` prevents multiple initializations
    // during Pytest runs.
    let _ = env_logger::builder().is_test(true).try_init();

    // Add the custom exception type to the Python module so it can be caught
    // by Python code.
    m.add("KaryakshamRustEngineError", _py.get_type::<KaryakshamRustEngineError>())?;

    // Add the exposed Rust functions to the Python module.
    // `wrap_pyfunction!` macro handles the necessary boilerplate for binding.
    m.add_function(wrap_pyfunction!(process_csv_file, m)?)?;
    m.add_function(wrap_pyfunction!(rust_hello_world, m)?)?;

    Ok(())
}