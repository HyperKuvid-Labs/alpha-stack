```python
import sys
import logging
import traceback

from PySide6.QtCore import QObject, QThread, Signal, Slot

# Project-specific imports
from sanchay_app.core.job_manager import JobManager
# The logging configuration is expected to be initialized once at application startup,
# for example, in __main__.py or sanchay_app/__init__.py.
# We just retrieve the logger here.
logger = logging.getLogger(__name__)

# Attempt to import the Rust core library
try:
    # This assumes the sanchay_core wheel is installed and available
    # It will be the `sanchay_core` package that Maturin builds from `crates/sanchay_core`
    import sanchay_core
    logger.info("Successfully imported sanchay_core Rust extension.")
except ImportError:
    logger.error(
        "sanchay_core Rust extension not found. "
        "Please ensure it's built and installed correctly via 'maturin develop' or 'pip install .'."
    )
    # Define a dummy Rust core for development/testing when the actual Rust extension
    # is not built or installed. This allows the application to run without the Rust core.
    class DummySanchayCore:
        """
        A placeholder for the Rust core functions when the actual Rust extension
        is not built or installed. Simulates operations with delays and respects
        the progress callback's return value for cancellation.
        """
        def process_directory(self, path: str, task_config: dict, progress_callback=None) -> dict:
            logger.warning(f"Using dummy sanchay_core.process_directory for path: {path}")
            import time
            total_items = 10000
            for i in range(1, total_items + 1):
                time.sleep(0.0001) # Simulate work
                if i % 100 == 0 or i == total_items:
                    message = f"Simulating processing: {i}/{total_items} items"
                    logger.debug(message)
                    if progress_callback:
                        # If callback returns False, it means cancellation was requested
                        if not progress_callback(i, total_items, message):
                            logger.info("Dummy processing cancelled via callback.")
                            return {"status": "cancelled", "processed_count": i - 1, "results": []}
            logger.info(f"Dummy sanchay_core.process_directory completed for {path}.")
            return {
                "status": "success",
                "processed_count": total_items,
                "results": [{"file": f"dummy_file_{i}.txt", "hash": f"dummy_hash_{i}"} for i in range(5)]
            }

        def find_duplicates(self, path: str, hash_algorithm: str, progress_callback=None) -> dict:
            logger.warning(f"Using dummy sanchay_core.find_duplicates for path: {path}")
            import time
            total_items = 5000
            for i in range(1, total_items + 1):
                time.sleep(0.0002)
                if i % 50 == 0 or i == total_items:
                    message = f"Simulating duplicate check: {i}/{total_items} files"
                    logger.debug(message)
                    if progress_callback:
                        if not progress_callback(i, total_items, message):
                            logger.info("Dummy duplicate finding cancelled via callback.")
                            return {"status": "cancelled", "duplicates_found": 0, "duplicates": []}
            logger.info(f"Dummy sanchay_core.find_duplicates completed for {path}.")
            return {
                "status": "success",
                "duplicates_found": 2,
                "duplicates": [
                    {"hash": "hash_a", "files": ["/path/to/a1.txt", "/path/to/a2.txt"]},
                    {"hash": "hash_b", "files": ["/path/to/b1.txt", "/path/to/b2.txt", "/path/to/b3.txt"]},
                ]
            }

    sanchay_core = DummySanchayCore()


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    These signals are used to communicate from the worker thread back to the
    main GUI thread, ensuring thread-safe UI updates.
    """
    finished = Signal()  # Emitted when the worker thread has completed its execution.
    error = Signal(tuple) # Emitted when an unhandled exception occurs in the worker.
                          # Contains (exctype, value, traceback.format_exc()).
    progress = Signal(int, int, str) # Emitted for progress updates:
                                     # (percentage_complete, files_processed_count, message).
    results = Signal(dict) # Emitted when the processing job yields final results.
    log_message = Signal(str, str) # Emitted for structured log messages from the worker:
                                   # (log_level_str, message_str).


class SanchayWorker(QThread):
    """
    A QThread worker for executing long-running file processing operations
    using the Sanchay Rust core. This ensures the GUI remains responsive by
    running intensive tasks on a separate thread.
    """
    def __init__(self, job_id: str, job_manager: JobManager, path: str, task_config: dict, parent=None):
        """
        Initializes the SanchayWorker.

        Args:
            job_id: A unique identifier for the processing job.
            job_manager: An instance of JobManager to update job states and retrieve job details.
            path: The root path (directory or S3 prefix) to process.
            task_config: A dictionary containing configuration for the specific task
                         (e.g., {'type': 'scan_and_hash', 'hash_algorithm': 'SHA256'}).
            parent: The parent QObject, typically None for top-level threads.
        """
        super().__init__(parent)
        self.job_id = job_id
        self.job_manager = job_manager
        self.path = path
        self.task_config = task_config
        self.signals = WorkerSignals()
        self._is_cancelled = False # Internal flag to signal cancellation to the Rust core

    def _rust_progress_callback(self, current_items: int, total_items: int, message: str) -> bool:
        """
        Callback function passed to the Rust core.
        It is invoked by Rust to report progress.
        This function runs in the context of the calling Rust thread (which PyO3 maps
        to a Python thread, but not necessarily the main Qt thread).
        Therefore, it must emit signals to communicate with the Qt main thread.

        Args:
            current_items: The number of items processed so far.
            total_items: The total number of items to process (if known).
            message: A descriptive message about the current progress.

        Returns:
            True if the operation should continue, False if cancellation is requested
            by the Python side, signaling the Rust core to stop cooperatively.
        """
        if self._is_cancelled:
            logger.debug(f"Cancellation detected by callback for job {self.job_id}.")
            return False # Signal to Rust to stop if it supports it

        try:
            percentage = 0
            if total_items > 0:
                percentage = int((current_items / total_items) * 100)
            
            # Emit progress update for the UI
            self.signals.progress.emit(percentage, current_items, message)
            
            # Update the job manager's internal state
            self.job_manager.update_job_progress(self.job_id, percentage, current_items, message)
            
            # You might also want to emit log_message from here for crucial updates
            # self.signals.log_message.emit("INFO", message)

            return True # Signal to Rust to continue
        except Exception as e:
            logger.error(f"Error in Rust progress callback for job {self.job_id}: {e}")
            exctype, value, tb_str = sys.exc_info()[0], sys.exc_info()[1], traceback.format_exc()
            self.signals.error.emit((exctype, value, tb_str))
            return False # Signal to Rust to stop due to error

    def run(self):
        """
        The main execution method for the thread.
        This method will call into the Rust core for the actual processing.
        """
        logger.info(f"Worker {self.job_id} started. Path: '{self.path}', Config: {self.task_config}")
        self.job_manager.start_job(self.job_id, self.path, self.task_config)

        try:
            task_type = self.task_config.get("type")
            if not task_type:
                raise ValueError("Task configuration must specify a 'type'.")

            results = None
            if task_type == "scan_and_hash":
                # Call the Rust function for scanning and hashing.
                # The Rust function must accept the path, task_config, and a progress callback.
                results = sanchay_core.process_directory(
                    self.path,
                    self.task_config,
                    self._rust_progress_callback # Pass the Python callable for progress
                )
            elif task_type == "find_duplicates":
                # Call the Rust function for finding duplicates.
                # Assumes it also takes a path, relevant config, and a progress callback.
                hash_algorithm = self.task_config.get("hash_algorithm", "SHA256")
                results = sanchay_core.find_duplicates(
                    self.path,
                    hash_algorithm, # Directly pass specific parameters for simpler tasks
                    self._rust_progress_callback
                )
            else:
                raise ValueError(f"Unsupported task type: '{task_type}'")

            if results and results.get("status") == "cancelled":
                # If Rust core explicitly returns a 'cancelled' status
                self.job_manager.cancel_job(self.job_id)
                logger.info(f"Job {self.job_id} was cancelled by Rust core.")
            elif results:
                self.signals.results.emit(results)
                self.job_manager.complete_job(self.job_id, results)
            else:
                # This case should ideally not happen if Rust always returns a dict
                # (even an empty one for 'cancelled' or 'failed' status)
                self.job_manager.fail_job(self.job_id, "No results returned from Rust core.")
                self.signals.error.emit((ValueError, "No results from Rust core", "N/A"))

        except Exception as e:
            # Catch any exception from the Python or Rust call
            exctype, value, tb_str = sys.exc_info()[0], sys.exc_info()[1], traceback.format_exc()
            self.signals.error.emit((exctype, value, tb_str))
            self.job_manager.fail_job(self.job_id, f"Error: {value}")
            logger.exception(f"Worker {self.job_id} encountered an error during '{task_type}' task.")
        finally:
            self.signals.finished.emit()
            logger.info(f"Worker {self.job_id} finished processing.")

    @Slot()
    def cancel(self):
        """
        Requests the worker to cancel its current operation.
        This sets an internal flag (`_is_cancelled`) which the `_rust_progress_callback`
        checks to signal the Rust core to stop cooperatively.
        It does not immediately terminate the thread. The Rust core must be designed
        to respond to this cancellation signal (e.g., by checking the return value
        of the progress callback and exiting its processing loop).
        """
        if not self._is_cancelled: # Only mark as cancelled once
            self._is_cancelled = True
            # Update job status in manager immediately to reflect requested cancellation
            self.job_manager.cancel_job(self.job_id) 
            logger.info(f"Cancellation requested for job {self.job_id}.")
        else:
            logger.debug(f"Cancellation already requested for job {self.job_id}.")

```