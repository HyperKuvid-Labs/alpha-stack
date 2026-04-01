import pytest
from src.core import process_data

def test_process_data_success():
    assert process_data(" hello ") == "HELLO"

def test_process_data_invalid_input():
    with pytest.raises(ValueError):
        process_data(123)
