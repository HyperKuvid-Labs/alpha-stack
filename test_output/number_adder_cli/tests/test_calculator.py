import pytest
from number_adder_cli.calculator import add

@pytest.mark.parametrize("num1, num2, expected", [
    (2, 3, 5),
    (100, 200, 300),
    (-2, -3, -5),
    (-10, 5, -5),
    (10, -5, 5),
    (0, 5, 5),
    (5, 0, 5),
    (0, 0, 0),
    (-5, 0, -5),
    (1.5, 2.5, 4.0),
    (-1.5, 2.5, 1.0),
    (1.23, 4.56, 5.79),
    (5, 2.5, 7.5),
    (-3.5, 1, -2.5),
    (1_000_000_000, 2_000_000_000, 3_000_000_000),
])
def test_add_various_numbers(num1, num2, expected):
    assert add(num1, num2) == expected

def test_add_floating_point_precision():
    assert add(0.1, 0.2) == pytest.approx(0.3)

@pytest.mark.parametrize("num1, num2", [
    ("a", 1),
    (1, "b"),
    ("a", "b"),
    (None, 1),
    (1, None),
    ([1, 2], 3),
    (3, {"a": 1}),
])
def test_add_raises_type_error_for_invalid_input(num1, num2):
    with pytest.raises(TypeError):
        add(num1, num2)
