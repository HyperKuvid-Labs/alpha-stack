import logging
import sys
from pythonjsonlogger import jsonlogger

from pravah.config.settings import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    A custom JSON formatter for application logs.
    It renames 'levelname' to 'level' and 'asctime' to 'timestamp' for consistency,
    and ensures common useful fields like 'pathname', 'lineno', 'funcName' are included.
    """
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Rename 'levelname' to 'level' and ensure it's uppercase
        if 'level' in log_record:
            log_record['level'] = log_record['level'].upper()
        elif 'levelname' in log_record:
            log_record['level'] = log_record.pop('levelname').upper()

        # Rename 'asctime' to 'timestamp'
        if 'asctime' in log_record:
            log_record['timestamp'] = log_record.pop('asctime')

        # Add other useful standard fields from the log record if not already present
        # These are commonly used for debugging and context.
        for field in ['pathname', 'lineno', 'funcName', 'process', 'thread', 'module']:
            if hasattr(record, field) and field not in log_record:
                log_record[field] = getattr(record, field)


def setup_logging():
    """
    Configures the application-wide logging using structured JSON format.
    Log level is loaded from application settings (environment variables).
    Logs are directed to stdout, which is standard for containerized applications.
    """
    log_level_str = settings.LOG_LEVEL.upper()
    numeric_log_level = getattr(logging, log_level_str, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_log_level)

    # Prevent adding multiple handlers if setup_logging is called more than once
    # (e.g., in tests or during application reloads in development).
    # This checks if a StreamHandler (our primary handler) already exists.
    if not any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers):
        # Create a StreamHandler that writes to standard output (sys.stdout).
        # This is crucial for Docker and Kubernetes log collection.
        handler = logging.StreamHandler(sys.stdout)

        # Define the format string for the JSON formatter.
        # This string specifies which standard `logging.LogRecord` attributes
        # should be processed and included in the JSON output.
        # Our `CustomJsonFormatter` will then rename/reformat them.
        formatter = CustomJsonFormatter(
            fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d %(funcName)s %(process)d %(thread)d %(module)s',
            datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Suppress overly verbose loggers from third-party libraries that might
    # spam logs at INFO level or lower. Adjust levels as needed for debugging.
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Used by FastAPI for internal HTTP calls
    logging.getLogger("fastapi").setLevel(logging.INFO)   # Keep FastAPI's own logs at INFO if useful

    # Log a confirmation message that logging has been set up.
    logging.info(f"Application logging initialized with level: {log_level_str}")

# This `setup_logging()` function should be called early in the application's
# lifecycle, typically in `pravah/app/main.py` when the FastAPI app starts.
# Example call:
# from pravah.app.utils.logging import setup_logging
# setup_logging()