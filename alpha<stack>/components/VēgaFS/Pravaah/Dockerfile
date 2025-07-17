# Stage 1: Build the Rust extension and generate the Python wheel
FROM rust:1.76-slim-bookworm AS rust_builder

# Set environment variables for non-interactive apt-get operations
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory inside the container
WORKDIR /app

# Install Python and pip, which are required for maturin
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install maturin, the build tool for Rust-Python integration
RUN pip install --no-cache-dir maturin

# Copy the pyproject.toml and the rust_core source directory.
# These paths are relative to the Docker build context (e.g., VēgaFS/Pravaah/).
COPY pyproject.toml .
COPY rust_core rust_core

# Build the Rust wheel.
# --release for optimized binary, --manylinux off for specific target,
# --strip to remove debug symbols, --locked to use Cargo.lock for reproducibility.
RUN maturin build --release --manylinux off --strip --locked

# Stage 2: Create the final application image
FROM python:3.10-slim-bookworm AS final

# Set essential environment variables for Python and Debian.
# PYTHONUNBUFFERED=1 ensures logs appear immediately.
# PYTHONDONTWRITEBYTECODE=1 prevents .pyc files from being written.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory inside the container for the application
WORKDIR /app

# Install system dependencies needed for Python packages (e.g., C compiler for C extensions).
# `gcc` and `python3-dev` are general dependencies for compiling Python packages with C extensions.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the pyproject.toml file, which defines the Python project and its dependencies.
# This path is relative to the Docker build context.
COPY pyproject.toml .

# Install the Python dependencies for the application from pyproject.toml.
# `--no-cache-dir` reduces image size by not storing pip's cache.
RUN pip install --no-cache-dir .

# Copy the pre-built Rust wheel from the `rust_builder` stage to a temporary location.
# The wheel name includes "vegafs_rust_core" as configured in pyproject.toml's maturin section.
COPY --from=rust_builder /app/target/wheels/vegafs_rust_core-*.whl /tmp/

# Install the Rust wheel into the final image's Python environment.
RUN pip install --no-cache-dir /tmp/vegafs_rust_core-*.whl

# Copy the actual Python application source code.
# This path is relative to the Docker build context.
COPY app app

# Expose the port on which FastAPI will listen.
EXPOSE 8000

# Define the command to run the application using Uvicorn.
# `app.main:app` refers to the 'app' FastAPI instance inside 'main.py' within the 'app' package.
# `--host 0.0.0.0` makes the server accessible from outside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]