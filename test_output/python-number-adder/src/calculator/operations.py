def add(a: int | float, b: int | float) -> int | float:
    if not isinstance(a, (int, float)):
        raise TypeError(f"Expected int or float, got {type(a).__name__}")
    if not isinstance(b, (int, float)):
        raise TypeError(f"Expected int or float, got {type(b).__name__}")
    return a + b
