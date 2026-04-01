"""Core business logic processing tools."""

def process_data(data: str) -> str:
    """
    Example business logic function.
    Processes string data and returns a transformed version.
    """
    if not isinstance(data, str):
        raise ValueError("Input must be a string")
    return data.strip().upper()
