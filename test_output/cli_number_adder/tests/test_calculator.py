import pytest
from src.calculator import add

@pytest.mark.parametrize("num1, num2, expected", [
    (5, 3, 8),
    (-5, -3, -8),
    (5, -3, 2),
    (-5, 3, -2),
    (0, 5, 5),
    (5, 0, 5),
    (0, 0, 0),
    (2.5, 3.5, 6.0),
    (-2.5, -3.5, -6.0),
    (10.5, -5.5, 5.0),
    (5, 2.5, 7.5),
    (2.5, 5, 7.5),
    (1_000_000_000, 2_000_000_000, 3_000_000_000),
    (0.1, 0.2, 0.3),
])
def test_add_valid_numbers(num1, num2, expected):
    assert add(num1, num2) == pytest.approx(expected)

@pytest.mark.parametrize("num1, num2", [
    ("5", 3),
    (5, "3"),
    ("hello", "world"),
    (None, 5),
    (5, None),
    ([1, 2], 3),
    (5, [1, 2]),
    ({"a": 1}, 5),
    (5, {"a": 1}),
])
def test_add_invalid_types_raises_type_error(num1, num2):
    with pytest.raises(TypeError):
        add(num1, num2)
