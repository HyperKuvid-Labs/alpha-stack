# Stage 1: Build the Rust core engine
FROM rust:1.77.2-bookworm AS builder-rust

# Install essential build tools and Python for maturin
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install maturin, the build tool for PyO3 Rust extensions
RUN pip install maturin==1.7.0

# Set the working directory to the root of the project inside the container
WORKDIR /pravah

# Copy the Rust core engine source code and the root pyproject.toml
# The pyproject.toml is needed by maturin to infer package metadata
COPY pravah_core/ ./pravah_core/
COPY pyproject.toml ./

# Change directory into the Rust crate and build the Python wheel
# --release: for an optimized production build
# --manylinux2014: ensures compatibility with a broad range of Linux distributions
# --out ../dist_wheels: specifies the output directory for the wheel relative to the current WORKDIR
WORKDIR /pravah/pravah_core
RUN maturin build --release --manylinux2014 --out ../dist_wheels

# Stage 2: Prepare Python Dependencies
FROM python:3.11-slim-bookworm AS builder-python-deps

# Set working directory for dependency preparation
WORKDIR /tmp

# Copy pyproject.toml and poetry.lock to leverage Docker's build cache
COPY pyproject.toml poetry.lock ./

# Install Poetry and use it to export dependencies to a requirements.txt file
# --without-hashes: simplifies the output for Docker layering, as pip's default caching is sufficient
# This ensures that pip can install the exact versions specified in poetry.lock
RUN pip install poetry==1.7.1 && \
    poetry export --without-hashes --format requirements.txt --output requirements.txt

# Install all Python dependencies into a dedicated directory
# --target: specifies a non-standard directory for installation, which makes copying easier in the final stage
RUN pip install -r requirements.txt --target=/pravah_deps

# Stage 3: Final production image
FROM python:3.11-slim-bookworm AS final

# Set environment variables for the application
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    UVICORN_PORT=8000 \
    LOG_LEVEL=INFO \
    # Provide default values for critical services; these should be overridden by secrets in production
    DATABASE_URL="postgresql://user:password@localhost:5432/pravah_db" \
    AWS_REGION="us-east-1" \
    S3_BUCKET_NAME="" # Placeholder, expected to be set at runtime

# Install necessary runtime system libraries for Python packages (e.g., libpq-dev for psycopg2)
# Add any other minimal runtime dependencies needed by your application here
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    # If the Rust engine or Python code interacts with specific file types (e.g., images),
    # corresponding libraries might be needed (e.g., libjpeg-dev, zlib1g-dev)
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for security best practices
RUN addgroup --system pravahgroup && adduser --system --ingroup pravahgroup pravahuser
USER pravahuser

# Set the application's working directory
WORKDIR /app

# Copy the Python application code and configuration
# --chown ensures the files are owned by the non-root user
COPY --chown=pravahuser:pravahuser app/ ./app/
COPY --chown=pravahuser:pravahuser config/ ./config/

# Copy the pre-installed Python dependencies from the `builder-python-deps` stage
# This copies all site-packages content into the final image's Python environment
COPY --from=builder-python-deps --chown=pravahuser:pravahuser /pravah_deps/ /usr/local/lib/python3.11/site-packages/

# Copy the built Rust wheel from the `builder-rust` stage to a temporary location
COPY --from=builder-rust --chown=pravahuser:pravahuser /pravah/dist_wheels/ /tmp/pravah_wheels/

# Install the Rust wheel using pip
# The wildcard `*.whl` handles dynamic wheel filenames (e.g., due to versioning or platform tags)
RUN pip install /tmp/pravah_wheels/*.whl \
    && rm -rf /tmp/pravah_wheels # Clean up the temporary wheel directory

# Expose the port on which the FastAPI application will listen
EXPOSE ${UVICORN_PORT}

# Define the command to run the FastAPI application using Uvicorn
# `app.main:app` refers to the `app` instance within `main.py` inside the `app` module
# `--host 0.0.0.0`: Binds Uvicorn to all available network interfaces
# `--port 8000`: Specifies the listening port
# `--log-level`: Uses the configured LOG_LEVEL environment variable
# `--workers 1`: For containerized deployments, it's common to run a single Uvicorn worker per container
# and scale horizontally using orchestration tools like Kubernetes.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "${LOG_LEVEL}", "--workers", "1"]