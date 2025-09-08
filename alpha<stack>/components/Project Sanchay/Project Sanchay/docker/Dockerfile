FROM rust:1.75.0-slim-bullseye AS rust_builder

# Install build dependencies for Python and Maturin
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    build-essential \
    pkg-config \
    libssl-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install maturin, pinning to the version range specified in pyproject.toml
RUN pip install "maturin>=0.14,<0.15"

WORKDIR /app

# Copy pyproject.toml and Cargo.lock first to leverage Docker cache.
# These files define dependencies and trigger re-builds less frequently.
COPY pyproject.toml /app/
COPY Cargo.lock /app/

# Copy the entire Rust crate folder, including Cargo.toml and src
COPY crates /app/crates

# Build the Rust extension (sanchay_core) and create the Python wheel for 'sanchay'.
# The wheel will be generated in /app/target/wheels/.
# maturin is configured via the root pyproject.toml to build the 'sanchay' project.
RUN maturin build --release --locked


FROM python:3.10-slim-bullseye AS python_runtime

# Set environment variables for non-buffered output, configuration, and default logging
ENV PYTHONUNBUFFERED=1 \
    APP_CONFIG=production \
    DATABASE_PATH=/app/sanchay_metadata.db \
    LOG_LEVEL=INFO \
    # Ensure UTF-8 locale for consistent string handling
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install runtime dependencies for the Python application.
# Includes SQLite library for database access.
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    libsqlite3-0 \
    # Add any other system runtime dependencies for Python libraries if needed
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the Python application code, configuration, assets, and README
# The 'src/sanchay_app' directory is expected to be the 'sanchay' Python package.
COPY src/sanchay_app /app/src/sanchay_app
COPY config /app/config
COPY assets /app/assets
COPY README.md /app/

# Copy the project's root pyproject.toml for installing Python dependencies.
# This file also defines the 'sanchay' project metadata.
COPY pyproject.toml /app/

# Copy the compiled Rust extension wheel from the builder stage.
# The wheel name is 'sanchay-<version>-...whl' based on pyproject.toml's 'project.name'.
COPY --from=rust_builder /app/target/wheels/sanchay-*.whl /app/

# Install the Python application and its dependencies.
# This will install the 'sanchay' package (including the Rust extension)
# and any other pure Python dependencies listed in pyproject.toml.
# Pip will find and use the copied wheel.
RUN pip install --no-cache-dir .

# Entry point for the application.
# The 'sanchay' package, stemming from 'src/sanchay_app', is run via its '__main__.py' module.
CMD ["python", "-m", "sanchay"]