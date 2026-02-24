from __future__ import annotations

# perimeter_of_square module
# Exposes a single pure function to compute the perimeter of a square from its side length.
# Includes strict input validation and returns a float.

from typing import Union


def perimeter_of_square(side: Union[int, float]) -> float:
    # Explicitly disallow booleans, which are a subclass of int
    if isinstance(side, bool) or not isinstance(side, (int, float)):
        raise TypeError('side must be a numeric type (int or float)')
    value = float(side)

    # Reject NaN values
    if value != value:
        raise ValueError('side must be non-negative')
    if value < 0:
        raise ValueError('side must be non-negative')

    return 4.0 * value

__all__ = ['perimeter_of_square']
