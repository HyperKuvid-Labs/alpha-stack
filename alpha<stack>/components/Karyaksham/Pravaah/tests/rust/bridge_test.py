import pytest
# It is assumed that 'karyaksham_rust_engine' is the name of the compiled Rust module
# as defined in rust_engine/Cargo.toml and built by maturin.
try:
    import karyaksham_rust_engine as rust_engine
except ImportError:
    pytest.fail(
        "Could not import the Rust engine. "
        "Ensure it is built and available in the Python environment. "
        "Run `maturin develop` or `maturin build --release && pip install dist/*.whl` "
        "from the rust_engine/ directory."
    )


def test_add_numbers_success():
    result = rust_engine.add_numbers(5, 7)
    assert result == 12
    assert isinstance(result, int)

    result_negative = rust_engine.add_numbers(-10, 3)
    assert result_negative == -7


def test_add_numbers_zero():
    result = rust_engine.add_numbers(0, 0)
    assert result == 0


def test_reverse_string_success():
    input_str = "hello"
    expected_str = "olleh"
    result = rust_engine.reverse_string(input_str)
    assert result == expected_str
    assert isinstance(result, str)

    result_empty = rust_engine.reverse_string("")
    assert result_empty == ""

    result_unicode = rust_engine.reverse_string("🚀 Rust")
    assert result_unicode == "tsuR 🚀"


def test_process_simple_data_uppercase():
    input_data = "Karyaksham efficient"
    transform_type = "uppercase"
    expected_output = "KARYAKSHAM EFFICIENT"
    result = rust_engine.process_simple_data(input_data, transform_type)
    assert result == expected_output


def test_process_simple_data_lowercase():
    input_data = "Karyaksham EFFICIENT"
    transform_type = "lowercase"
    expected_output = "karyaksham efficient"
    result = rust_engine.process_simple_data(input_data, transform_type)
    assert result == expected_output


def test_process_simple_data_invalid_transform():
    input_data = "some data"
    transform_type = "invalid_transform"
    with pytest.raises(ValueError) as excinfo:
        rust_engine.process_simple_data(input_data, transform_type)
    assert "Invalid transform type" in str(excinfo.value)