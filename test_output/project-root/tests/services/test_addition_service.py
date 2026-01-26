import pytest
from src.services.addition_service import add_numbers

@pytest.mark.parametrize("num1, num2, expected_sum", [
    (5, 10, 15),
    (-5, -10, -15),
    (5, -10, -5),
    (-5, 10, 5),
    (0, 10, 10),
    (-10, 0, -10),
    (0, 0, 0),
    (1000000000, 2000000000, 3000000000),
])
def test_add_numbers_with_integers(num1, num2, expected_sum):
    result = add_numbers(num1, num2)
    assert isinstance(result, int)
    assert result == expected_sum

@pytest.mark.parametrize("num1, num2, expected_sum", [
    (2.5, 3.5, 6.0),
    (-2.5, -3.5, -6.0),
    (2.5, -3.5, -1.0),
    (-2.5, 3.5, 1.0),
    (0.0, 5.5, 5.5),
    (-5.5, 0.0, -5.5),
    (0.1, 0.2, 0.3),
    (1e-9, 2e-9, 3e-9),
])
def test_add_numbers_with_floats(num1, num2, expected_sum):
    result = add_numbers(num1, num2)
    assert isinstance(result, float)
    assert result == pytest.approx(expected_sum)

@pytest.mark.parametrize("num1, num2, expected_sum", [
    (5, 2.5, 7.5),
    (2.5, 5, 7.5),
    (-5, 2.5, -2.5),
    (2.5, -5, -2.5),
    (0, 5.5, 5.5),
    (5.5, 0, 5.5),
])
def test_add_numbers_with_mixed_types(num1, num2, expected_sum):
    result = add_numbers(num1, num2)
    assert isinstance(result, float)
    assert result == pytest.approx(expected_sum)

@pytest.mark.parametrize("num1, num2", [
    ("5", 10),
    (5, "10"),
    ("5", "10"),
    (None, 10),
    (5, None),
    ([1, 2], 3),
    (5, {"a": 1}),
    (True, 5)
])
def test_add_numbers_with_invalid_types_raises_type_error(num1, num2):
    with pytest.raises(TypeError):
        add_numbers(num1, num2)
