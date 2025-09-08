import logging
import os
import sys
from pathlib import Path

# Define log format - this provides a "structured" human-readable output
# suitable for initial MVP, can be switched to JSONFormatter later if needed.
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(process)d | %(threadName)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logging(
    log_level_str: str = None,
    log_file_path: str = None,
    console_logging_enabled: bool = True,
    file_logging_enabled: bool = True
) -> None:
    """
    Configures the application's logging system.

    This function sets up console and optionally file logging, applying a consistent
    format and allowing log levels to be configured via arguments or environment variables.
    It clears any existing handlers to prevent duplicate log messages.

    Environment variables considered (prefixed with SANCHAY_ to avoid conflicts):
    - SANCHAY_LOG_LEVEL: (e.g., "INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL")
    - SANCHAY_LOG_FILE_PATH: Full path to the log file (e.g., "/var/log/sanchay/app.log")

    Args:
        log_level_str (str, optional): The desired logging level as a string.
                                        Overrides the SANCHAY_LOG_LEVEL environment variable.
                                        Defaults to "INFO" if not specified and no env var.
        log_file_path (str, optional): The path to the log file.
                                        Overrides the SANCHAY_LOG_FILE_PATH environment variable.
                                        If None and no env var, file logging is disabled.
        console_logging_enabled (bool): If True, logs will be output to the console (sys.stdout).
                                        Defaults to True.
        file_logging_enabled (bool): If True, logs will be written to the specified log file.
                                     Requires log_file_path to be provided or set via env var.
                                     Defaults to True.
    """
    # Get the root logger, which is the parent of all other loggers
    root_logger = logging.getLogger()
    # Set the root logger's level to DEBUG to ensure all messages are passed to handlers.
    # Individual handlers will then filter messages based on their own levels.
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers to prevent duplicate logs if setup_logging is called multiple times
    # (e.g., in tests or different entry points during development).
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close() # Important to close file handlers to release file locks

    # Determine the effective log level from arguments or environment variable
    effective_log_level_str = (
        log_level_str or os.getenv("SANCHAY_LOG_LEVEL", "INFO")
    ).upper()
    try:
        effective_log_level = getattr(logging, effective_log_level_str)
    except AttributeError:
        # Fallback to INFO if an invalid log level string is provided
        effective_log_level = logging.INFO
        # Log this warning using print to stderr as logging might not be fully configured yet
        print(
            f"WARNING: Invalid log level '{effective_log_level_str}' found in "
            f"arguments or SANCHAY_LOG_LEVEL environment variable. Defaulting to INFO.",
            file=sys.stderr
        )

    # Create a formatter for consistent log message structure
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Get a logger for this configuration module for internal messages
    config_logger = logging.getLogger(__name__)

    # --- Console Handler Setup ---
    if console_logging_enabled:
        console_handler = logging.StreamHandler(sys.stdout) # Explicitly use stdout
        console_handler.setFormatter(formatter)
        console_handler.setLevel(effective_log_level)
        root_logger.addHandler(console_handler)

    # --- File Handler Setup ---
    effective_log_file_path = log_file_path or os.getenv("SANCHAY_LOG_FILE_PATH")
    if file_logging_enabled and effective_log_file_path:
        log_file_path_obj = Path(effective_log_file_path)
        log_dir = log_file_path_obj.parent

        # Ensure the log directory exists
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                # If directory creation fails, log the error and disable file logging
                config_logger.error(f"Failed to create log directory {log_dir}: {e}. File logging will be disabled.")
                effective_log_file_path = None # Disable file logging for this run

        if effective_log_file_path: # Check again in case it was disabled above
            try:
                # Use FileHandler for basic file logging. Consider RotatingFileHandler
                # for production to prevent single large log files.
                file_handler = logging.FileHandler(
                    effective_log_file_path, encoding="utf-8"
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(effective_log_level)
                root_logger.addHandler(file_handler)
            except OSError as e:
                config_logger.error(
                    f"Failed to open log file {effective_log_file_path}: {e}. "
                    "File logging will be disabled."
                )
                effective_log_file_path = None # Disable file logging

    # Final check: if no handlers were successfully set up, print a critical message to stderr
    if not root_logger.handlers:
        print(
            "CRITICAL: No logging handlers could be configured. "
            "Application will run without logging output. "
            "Please check SANCHAY_LOG_LEVEL, SANCHAY_LOG_FILE_PATH environment variables "
            "or arguments, and ensure directory/file permissions are correct.",
            file=sys.stderr,
        )
    else:
        # Log a confirmation message through the newly configured system
        config_logger.info(
            f"Logging initialized. Level: {effective_log_level_str}. "
            f"Console enabled: {console_logging_enabled}. "
            f"File logging {'enabled' if effective_log_file_path else 'disabled'}: "
            f"{effective_log_file_path if effective_log_file_path else 'N/A'}."
        )