import uuid
from datetime import datetime, timezone
import math
import re
from pathlib import Path

def generate_unique_id() -> str:
    """Generates a unique identifier (UUID4) as a string."""
    return str(uuid.uuid4())

def get_current_utc_timestamp() -> datetime:
    """Returns the current UTC datetime with timezone information."""
    return datetime.now(timezone.utc)

def format_file_size(num_bytes: int) -> str:
    """
    Formats a number of bytes into a human-readable string (e.g., '1.2 GB').
    """
    if num_bytes == 0:
        return "0 Bytes"
    if num_bytes < 0:
        return "Invalid Size" # Or raise ValueError, depending on desired strictness

    sizes = ("Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(num_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(num_bytes / p, 2)
    return f"{s} {sizes[i]}"

def is_valid_filename(filename: str) -> bool:
    """
    Checks if a filename is valid and safe for storage and display.
    Disallows directory traversal, reserved names, and common unsafe characters.
    It does not check for uniqueness or existence on a filesystem.
    """
    if not isinstance(filename, str) or not filename.strip():
        return False

    # Prohibit directory traversal sequences and path separators
    if ".." in filename or "/" in filename or "\\" in filename:
        return False

    # Prohibit reserved names (common across Windows/Unix limitations)
    # This list is not exhaustive but covers the most common problematic names
    reserved_names = {
        "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4",
        "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2",
        "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"
    }
    if filename.lower() in reserved_names:
        return False

    # Disallow common characters problematic in filenames/paths (e.g., control characters, wildcards)
    # This regex matches any character that is NOT alphanumeric, a space, underscore, dash, or period.
    # It also explicitly disallows common filesystem special characters like <>:"/\|?*
    unsafe_chars_pattern = re.compile(r'[<>:"/\\|?*\x00-\x1F]') # Add control characters
    if unsafe_chars_pattern.search(filename):
        return False

    # Check byte length to prevent issues with filesystem limits, especially for UTF-8 names.
    # Most filesystems have a 255-byte limit for path components. S3 keys can be up to 1024 bytes.
    # For a general filename helper, 255 bytes is a good conservative limit.
    if len(filename.encode('utf-8')) > 255:
        return False

    return True

def sanitize_object_key(key: str) -> str:
    """
    Sanitizes a string to be suitable as an object storage key (e.g., S3, MinIO).
    Converts to lowercase, replaces unsafe characters with a dash, and trims dashes.
    Ensures the key is not empty and falls back to a UUID if input is entirely invalid.
    """
    if not isinstance(key, str) or not key.strip():
        return generate_unique_id() # Fallback for empty or whitespace-only input

    # Convert to lowercase to normalize keys
    sanitized_key = key.lower()

    # Replace any character that is NOT alphanumeric, an underscore, a dash, or a period with a dash.
    # This also handles spaces and most special characters by replacing them with a dash.
    sanitized_key = re.sub(r'[^a-z0-9_.-]+', '-', sanitized_key)

    # Remove leading/trailing dashes that might result from sanitization
    sanitized_key = sanitized_key.strip('-')

    # Remove multiple consecutive dashes
    sanitized_key = re.sub(r'-{2,}', '-', sanitized_key)

    # Ensure the key is not empty after sanitization; fallback to a unique ID if it is.
    if not sanitized_key:
        return generate_unique_id()

    # Object storage keys have limits (e.g., S3 is 1024 bytes, MinIO is similar).
    # Trimming to a reasonable length to prevent extremely long keys.
    # 200 characters is a good balance for readability and practicality.
    if len(sanitized_key) > 200:
        sanitized_key = sanitized_key[:200]

    return sanitized_key