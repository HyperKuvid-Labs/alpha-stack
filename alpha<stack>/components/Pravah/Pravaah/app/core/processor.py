import logging
from pathlib import Path
from typing import Dict, Any, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

# Attempt to import the Rust core module.
# This module is built by maturin and will be available in the Python environment
# as 'pravah_core'.
try:
    import pravah_core
except ImportError:
    logging.error(
        "Pravah Rust core engine not found. "
        "Please ensure 'pravah_core' is built and installed. "
        "Run `maturin develop` or `pip install .` in the pravah_core directory."
    )
    # Re-raise to ensure the application doesn't start without its core component
    raise PravahProcessorInitializationError("Pravah Rust core engine (pravah_core) not found.")


# --- Pydantic Models for Configuration and Results ---

class InputOptions(BaseModel):
    """Defines how files are selected for processing."""
    recursive: bool = Field(default=True, description="Whether to scan directories recursively.")
    include_patterns: List[str] = Field(
        default_factory=list,
        description="Glob patterns (e.g., '*.csv', 'data/*.log') to include files. Empty means all."
    )
    exclude_patterns: List[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude files."
    )
    min_size_bytes: Optional[int] = Field(
        default=None, ge=0,
        description="Minimum file size in bytes to include. None for no minimum."
    )
    max_size_bytes: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum file size in bytes to include. None for no maximum."
    )

class S3OutputConfig(BaseModel):
    """Configuration for S3 output."""
    bucket_name: str = Field(..., description="S3 bucket name.")
    region: Optional[str] = Field(default=None, description="AWS region for the S3 bucket.")
    endpoint_url: Optional[str] = Field(
        default=None,
        description="Custom S3 endpoint URL (e.g., for MinIO).",
        examples=["http://localhost:9000"]
    )
    # Credentials should typically be managed via environment variables or IAM roles,
    # but can be added here if needed for specific use cases.
    # access_key_id: Optional[str] = None
    # secret_access_key: Optional[str] = None

class OutputOptions(BaseModel):
    """Defines where and how processed files are stored."""
    output_path: str = Field(
        ...,
        description="Base path or S3 prefix for output. For S3, this is the key prefix."
    )
    destination_type: Literal["local_fs", "s3"] = Field(
        ...,
        description="Type of storage destination: 'local_fs' or 's3'."
    )
    s3_config: Optional[S3OutputConfig] = Field(
        default=None,
        description="S3-specific configuration if destination_type is 's3'."
    )

    # Note: Pydantic v2's `model_validator` or field validation can enforce
    # `s3_config` presence when `destination_type` is 's3'.
    # Example (add to class):
    # from pydantic import model_validator
    # @model_validator(mode='after')
    # def check_s3_config_if_s3_destination(self) -> 'OutputOptions':
    #     if self.destination_type == 's3' and self.s3_config is None:
    #         raise ValueError("s3_config must be provided if destination_type is 's3'")
    #     return self


class ProcessingConfig(BaseModel):
    """Defines the specific operation and its parameters."""
    operation: Literal[
        "extract_csv_headers",
        "compress_files",
        "resize_images",
        "count_lines",
        "noop" # A no-op operation for testing file traversal without actual processing
    ] = Field(..., description="The type of processing operation to perform.")
    operation_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters specific to the chosen operation (e.g., 'compression_level', 'target_width')."
    )

class ProcessJobInput(BaseModel):
    """Input structure for a processing job."""
    input_path: str = Field(..., description="The root path or S3 prefix to start scanning from.")
    input_type: Literal["local_fs", "s3"] = Field(
        ...,
        description="Type of input source: 'local_fs' or 's3'."
    )
    input_options: InputOptions = Field(
        default_factory=InputOptions,
        description="Options for file selection and traversal."
    )
    processing_config: ProcessingConfig = Field(
        ...,
        description="Configuration for the specific processing operation."
    )
    output_options: OutputOptions = Field(
        ...,
        description="Configuration for the output destination."
    )
    job_id: str = Field(..., description="Unique ID for the job, used for tracking and logging.")


class FileProcessingResult(BaseModel):
    """Details for a single file's processing outcome."""
    file_path: str = Field(..., description="Path of the processed file.")
    success: bool = Field(..., description="True if processing was successful, False otherwise.")
    message: Optional[str] = Field(default=None, description="Success or error message.")
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional structured details, e.g., extracted headers, new file size."
    )

class ProcessJobResult(BaseModel):
    """Overall result of a processing job."""
    job_id: str = Field(..., description="The ID of the job that completed.")
    total_files_scanned: int = Field(..., description="Total number of files found and considered.")
    total_files_processed: int = Field(..., description="Total number of files attempted to process.")
    files_succeeded: int = Field(..., description="Number of files successfully processed.")
    files_failed: int = Field(..., description="Number of files that failed processing.")
    processing_duration_ms: int = Field(..., description="Total time taken for processing in milliseconds.")
    overall_status: Literal["completed", "completed_with_errors", "failed"] = Field(
        ...,
        description="Overall status of the job."
    )
    file_results: List[FileProcessingResult] = Field(
        default_factory=list,
        description="Detailed results for each processed file (can be limited for large jobs to prevent excessive memory usage)."
    )
    error_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary of overall errors if the job failed or completed with errors."
    )


# --- Processor Class ---

class PravahProcessor:
    """
    Manages the interaction with the high-performance Rust core engine.
    This class acts as a bridge, converting Python data structures to Rust-compatible
    formats and vice-versa, and orchestrating the processing tasks.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # pravah_core should expose a __version__ attribute if properly built with maturin
        self.logger.info("PravahProcessor initialized. Rust core engine version: %s",
                         getattr(pravah_core, '__version__', 'unknown'))

    async def process_job(self, job_input: ProcessJobInput) -> ProcessJobResult:
        """
        Submits a processing job to the Rust core engine and awaits its completion.

        Args:
            job_input: An instance of ProcessJobInput containing all job details.

        Returns:
            An instance of ProcessJobResult with the outcome of the processing.

        Raises:
            PravahProcessorError: If the Rust engine encounters an unrecoverable error
                                  or returns an invalid result.
        """
        self.logger.info(
            f"Submitting job '{job_input.job_id}' to Rust core. "
            f"Input: {job_input.input_path} ({job_input.input_type}), "
            f"Operation: {job_input.processing_config.operation}"
        )

        try:
            # Convert Pydantic model to a Python dictionary.
            # PyO3 efficiently maps Python dictionaries, lists, strings, and numbers
            # to Rust types like HashMap, Vec, String, int, bool, float when
            # the Rust function's signature uses `PyDict` or `FromPyObject` for these types.
            rust_input_data = job_input.model_dump()
            
            # Call the asynchronous Rust function.
            # It is assumed that `pravah_core.run_processing_job` is an `async fn`
            # exposed via PyO3, which can be `await`ed in Python.
            raw_rust_result = await pravah_core.run_processing_job(rust_input_data)
            
            # Convert the raw Rust result (which comes as a Python dict) back to Pydantic model.
            job_result = ProcessJobResult.model_validate(raw_rust_result)
            
            self.logger.info(
                f"Job '{job_input.job_id}' completed by Rust core. "
                f"Status: {job_result.overall_status}, "
                f"Processed: {job_result.files_succeeded}/{job_result.total_files_scanned} files "
                f"in {job_result.processing_duration_ms} ms."
            )
            return job_result

        # Catch specific errors from the Rust core, assuming they are exposed as Python exceptions.
        except getattr(pravah_core, 'PravahCoreError', Exception) as e:
            self.logger.error(f"Rust core engine error for job '{job_input.job_id}': {e}", exc_info=True)
            raise PravahProcessorError(
                f"Error from Pravah Rust core for job '{job_input.job_id}': {e}"
            ) from e
        
        # Catch Pydantic validation errors if the Rust output doesn't match the schema.
        except ValidationError as e:
            self.logger.error(
                f"Data validation error when converting Rust result for job '{job_input.job_id}': {e}",
                exc_info=True
            )
            raise PravahProcessorError(
                f"Failed to validate Rust core output for job '{job_input.job_id}': {e}"
            ) from e
        
        # Catch any other unexpected errors during the interaction.
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred while calling Rust core for job '{job_input.job_id}': {e}",
                exc_info=True
            )
            raise PravahProcessorError(
                f"An unexpected error occurred while calling Rust core for job '{job_input.job_id}': {e}"
            ) from e


class PravahProcessorError(Exception):
    """Custom exception for errors originating from the PravahProcessor or Rust core interaction."""
    pass

class PravahProcessorInitializationError(Exception):
    """Custom exception for errors during PravahProcessor initialization (e.g., Rust core missing)."""
    pass