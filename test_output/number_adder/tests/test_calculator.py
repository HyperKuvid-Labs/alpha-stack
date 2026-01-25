import pytest
from src.calculator import add

@pytest.mark.parametrize("num1, num2, expected", [
    (2, 3, 5),
    (-2, -3, -5),
    (5, -3, 2),
    (-10, 5, -5),
    (0, 0, 0),
    (100, 0, 100),
    (0, -50, -50),
    (1_000_000, 2_500_000, 3_500_000),
    (-1_000_000, -2_500_000, -3_500_000)
])
def test_add_integers(num1, num2, expected):
    assert add(num1, num2) == expected

@pytest.mark.parametrize("num1, num2, expected", [
    (1.5, 2.5, 4.0),
    (-1.5, -2.5, -4.0),
    (5.0, -2.5, 2.5),
    (0.0, 0.0, 0.0),
    (10.5, 0.0, 10.5),
    (0.1, 0.2, 0.3)
])
def test_add_floats(num1, num2, expected):
    assert add(num1, num2) == pytest.approx(expected)

@pytest.mark.parametrize("num1, num2, expected", [
    (5, 2.5, 7.5),
    (-5, -2.5, -7.5),
    (10, -5.5, 4.5),
    (0, 7.7, 7.7),
])
def test_add_mixed_numeric_types(num1, num2, expected):
    assert add(num1, num2) == pytest.approx(expected)

@pytest.mark.parametrize("num1, num2", [
    ("2", 3),
    (2, "3"),
    ("a", "b"),
    (None, 5),
    (5, None),
    ([1, 2], 3),
    (4, {"a": 1}),
    (True, 1)
])
def test_add_raises_type_error_for_invalid_inputs(num1, num2):
    with pytest.raises(TypeError):
        add(num1, num2)
