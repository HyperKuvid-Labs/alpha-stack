import pytest
from src.utils.validators import is_valid_number

@pytest.mark.parametrize("valid_input", [
    5,
    -10,
    0,
    3.14,
    -0.5,
    "123",
    "-45",
    "99.9",
    "-1.23",
    "0.0",
    "0"
])
def test_is_valid_number_returns_true_for_valid_numbers(valid_input):
    assert is_valid_number(valid_input) is True

@pytest.mark.parametrize("invalid_input", [
    True,
    False,
    "hello",
    "12a",
    "",
    "   ",
    None,
    [],
    {},
    (),
    object()
])
def test_is_valid_number_returns_false_for_invalid_inputs(invalid_input):
    assert is_valid_number(invalid_input) is False

def test_is_valid_number_handles_boolean_explicitly():
    assert is_valid_number(True) is False
    assert is_valid_number(False) is False

def test_is_valid_number_handles_none():
    assert is_valid_number(None) is False
