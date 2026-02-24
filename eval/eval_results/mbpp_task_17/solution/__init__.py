from __future__ import annotations

from typing import Union


def perimeter_of_square(side: Union[int, float]) -> float:
    # Disallow booleans explicitly; bool is a subclass of int
    if isinstance(side, bool) or not isinstance(side, (int, float)):
        raise TypeError('side must be a numeric type (int or float)')
    value = float(side)

    # NaN check and non-negativity
    if value != value:
        raise ValueError('side must be non-negative')
    if value < 0:
        raise ValueError('side must be non-negative')

    return 4.0 * value


__all__ = ["perimeter_of_square"]
