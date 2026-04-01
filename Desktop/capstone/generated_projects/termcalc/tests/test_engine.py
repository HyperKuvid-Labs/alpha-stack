import pytest
from calc.engine import CalculatorEngine

def calculate(expression):
    return CalculatorEngine.calculate(expression)

def test_basic_arithmetic():
    assert calculate("2 + 2") == 4
    assert calculate("10 - 5") == 5
    assert calculate("3 * 4") == 12
    assert calculate("20 / 4") == 5

def test_order_of_operations():
    assert calculate("2 + 3 * 4") == 14
    assert calculate("(2 + 3) * 4") == 20

def test_division_by_zero():
    # The current engine raises ValueError from ZeroDivisionError
    with pytest.raises(ValueError):
        calculate("10 / 0")

def test_invalid_syntax():
    # The current engine handles errors by raising ValueError
    with pytest.raises(ValueError):
        calculate("2 ++ 2")
    with pytest.raises(ValueError):
        calculate("abc + 1")
    with pytest.raises(ValueError):
        calculate("5 + ")
