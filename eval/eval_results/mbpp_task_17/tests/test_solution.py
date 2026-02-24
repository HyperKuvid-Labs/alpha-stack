import pytest
import importlib.util
from pathlib import Path

# Dynamically load the solution module from the repository root to avoid path issues during tests.
solution_path = Path(__file__).resolve().parents[1] / "solution.py"
spec = importlib.util.spec_from_file_location("solution", str(solution_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
perimeter_of_square = module.perimeter_of_square


def test_perimeter_with_zero_side_returns_zero_float():
    res = perimeter_of_square(0)
    assert res == 0.0
    assert isinstance(res, float)


def test_perimeter_with_integer_side_returns_float():
    res = perimeter_of_square(4)
    assert res == 16.0
    assert isinstance(res, float)


def test_perimeter_with_float_side_returns_float():
    res = perimeter_of_square(2.5)
    assert res == 10.0
    assert isinstance(res, float)


def test_perimeter_with_large_value():
    res = perimeter_of_square(1e6)
    assert res == 4e6
    assert isinstance(res, float)


def test_negative_side_raises_value_error():
    with pytest.raises(ValueError):
        perimeter_of_square(-1)


def test_nan_input_raises_value_error():
    with pytest.raises(ValueError):
        perimeter_of_square(float('nan'))


def test_bool_input_raises_type_error():
    with pytest.raises(TypeError):
        perimeter_of_square(True)


def test_non_numeric_input_raises_type_error():
    with pytest.raises(TypeError):
        perimeter_of_square("3")
