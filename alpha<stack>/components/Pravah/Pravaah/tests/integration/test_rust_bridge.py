import pytest
import asyncio

# The 'pravah_core' module is expected to be available in the Python environment
# as it's built by maturin. If running tests directly without a proper maturin build
# or `maturin develop` in the active environment, this import will fail.
# In a typical CI/CD or local development setup (e.g., via `pip install -e .` or `maturin develop`),
# the 'pravah_core' package will be discoverable.
try:
    import pravah_core
except ImportError:
    # This indicates the Rust module is not correctly built or linked.
    # In a real test environment (e.g., CI/CD), this would be an error
    # implying a problem with the build step. For local dev, ensure
    # `maturin develop` has been run from the project root.
    pytest.skip(
        "Could not import 'pravah_core'. "
        "Ensure the Rust module is built and available in your Python environment "
        "(e.g., by running `maturin develop` in the project root)."
    )

# Required for async tests with pytest
pytest_plugins = ("pytest_asyncio",)


class TestRustBridge:
    """
    Integration tests for the Python-Rust bridge (`pravah_core`).
    Verifies that Python can correctly call the compiled Rust functions,
    pass data, and handle any returned values or errors as expected.
    """

    def test_hello_pravah_sync(self):
        """
        Tests a simple synchronous function call to the Rust core.
        Verifies that a basic string message is returned.
        """
        result = pravah_core.hello_pravah()
        assert isinstance(result, str)
        assert "Hello from Pravah Rust core!" in result
        assert result == "Hello from Pravah Rust core!"

    def test_sum_numbers_sync(self):
        """
        Tests passing primitive integer types to a Rust function and
        receiving a calculated integer result.
        """
        num1 = 10
        num2 = 20
        result = pravah_core.sum_numbers(num1, num2)
        assert isinstance(result, int)
        assert result == 30

        num3 = -5
        num4 = 15
        result_neg = pravah_core.sum_numbers(num3, num4)
        assert result_neg == 10

    @pytest.mark.asyncio
    async def test_process_dummy_files_async(self):
        """
        Tests an asynchronous Rust function that simulates file processing.
        It verifies that a list of file paths can be passed along with a
        configuration, and that a structured list of results (Python objects
        converted from Rust structs) is returned correctly.
        """
        # Dummy file paths simulating input to the processing engine
        dummy_paths = [
            "/path/to/documents/report_q1_success.docx",
            "/data/logs/app_error.log",
            "/data/images/photo_gallery/img_001.jpg",
            "/archive/legacy_data/old_schema_failed.csv",
        ]

        # Dummy configuration that might be passed to the Rust engine
        dummy_config = {
            "processing_mode": "extract_metadata",
            "output_format": "json",
            "skip_errors": False,
            "compression_level": 5,
        }

        # Call the asynchronous Rust function and await its result
        results = await pravah_core.process_dummy_files(dummy_paths, dummy_config)

        # Assert that the result is a list and has the expected number of items
        assert isinstance(results, list)
        assert len(results) == len(dummy_paths)

        # Verify the structure and content of each returned item (which are Python
        # objects created from Rust's ProcessedFileResult struct)
        for i, res in enumerate(results):
            # Check if attributes exist (from PyO3's #[pyo3(get)] or #[pyclass] fields)
            assert hasattr(res, 'path')
            assert hasattr(res, 'size_bytes')
            assert hasattr(res, 'processed_successfully')
            assert hasattr(res, 'message')

            # Verify data types and specific values
            assert res.path == dummy_paths[i]
            assert isinstance(res.size_bytes, int)
            assert res.size_bytes >= 0 # Size should be non-negative

            if "success" in dummy_paths[i]:
                assert res.processed_successfully is True
                assert res.message is None # Successful processing implies no error message
            elif "error" in dummy_paths[i] or "failed" in dummy_paths[i]:
                assert res.processed_successfully is False
                assert isinstance(res.message, str)
                assert f"Failed to process {dummy_paths[i]}" in res.message
            else:
                # For paths without "success" or "failed" in name, assume success for dummy
                assert res.processed_successfully is True
                assert res.message is None

    def test_invalid_input_type_propagation(self):
        """
        Tests that invalid Python input types passed to Rust functions
        result in appropriate Python exceptions (e.g., TypeError).
        PyO3 handles type conversions and should raise an error if a conversion fails.
        """
        # Attempt to pass strings to a function expecting integers
        with pytest.raises((TypeError, ValueError)): # PyO3 usually raises TypeError for type mismatches
            pravah_core.sum_numbers("invalid", 10)

        with pytest.raises((TypeError, ValueError)):
            pravah_core.sum_numbers(5, None)

        # Attempt to pass a non-list to a function expecting a list of paths
        # This will likely fail within PyO3's argument parsing
        with pytest.raises((TypeError, ValueError)):
            # Assuming process_dummy_files expects Vec<String> for paths
            asyncio.run(pravah_core.process_dummy_files("not_a_list", {"mode": "test"}))

    @pytest.mark.asyncio
    async def test_empty_input_for_processing(self):
        """
        Tests handling of empty input lists for processing functions.
        """
        empty_paths = []
        dummy_config = {"mode": "noop"}
        results = await pravah_core.process_dummy_files(empty_paths, dummy_config)

        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_rust_side_error_propagation(self):
        """
        Tests that an error explicitly raised in Rust (e.g., via `PyErr::new_err`)
        is correctly propagated as a Python exception.
        This test assumes a specific Rust function `simulate_error` that is designed
        to throw an error.
        """
        # This test requires a Rust function specifically implemented to raise a Python error.
        # For example, in pravah_core/src/lib.rs:
        # #[pyfunction]
        # fn simulate_error() -> PyResult<()> {
        #    Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Simulated Rust error for testing!"))
        # }
        if not hasattr(pravah_core, 'simulate_error'):
            pytest.skip("pravah_core.simulate_error not found. Add this function to Rust core for error testing.")

        with pytest.raises(ValueError, match="Simulated Rust error for testing!"):
            await pravah_core.simulate_error()

    # Further tests could include:
    # - Testing more complex data structures (e.g., nested lists of structs/dictionaries)
    # - Performance benchmarking (typically in a separate benchmark suite)
    # - Testing resource management (e.g., file handles, memory cleanup) if applicable
    # - Testing concurrency limits or thread pool usage within Rust from Python's perspective.