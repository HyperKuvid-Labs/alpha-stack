# Stage 1: Build the Rust engine and create the Python wheel
FROM rust:1.76-slim-bookworm AS rust_builder

# Install Python and pip inside the Rust builder image, needed for maturin
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Rust project files, ensuring Cargo.lock is present for reproducible builds
# These paths are relative to the build context root (karyaksham/)
COPY rust_engine/Cargo.toml rust_engine/Cargo.lock ./rust_engine/
COPY rust_engine/src ./rust_engine/src/

# Install maturin to build the Rust library into a Python wheel
# Pinning maturin version for consistency
RUN pip install maturin==1.2.0

# Build the Rust library as a Python wheel
# maturin will place the wheel in target/wheels relative to the rust_engine dir
RUN cd rust_engine && maturin build --release --out target/wheels


# Stage 2: Build the final application image
FROM python:3.11-slim-bookworm AS final_app

# Set non-interactive mode for apt-get for a smoother build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies needed at runtime or for building Python packages
# build-essential: For compiling Python packages with C extensions (e.g., psycopg2-binary)
# libpq-dev: PostgreSQL client library, required by psycopg2-binary
# tini: An init system that handles signal forwarding and zombie processes, good for containers
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the application. All app-related files will be stored here.
WORKDIR /app

# Create a non-root user to run the application for security best practices
# --system creates a system user, --gid and --uid specify fixed IDs
# --home-dir /app and --no-create-home means home directory is /app but not created by useradd
RUN groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser --home-dir /app --no-create-home appuser

# Switch to the non-root user. All subsequent commands will run as 'appuser'.
USER appuser

# Copy Python project metadata and lock file first to leverage Docker cache.
# If these files don't change, Docker can reuse this layer.
# Chown ensures the files are owned by 'appuser'.
# Paths are relative to the build context (root of the project).
COPY --chown=appuser:appuser backend/pyproject.toml backend/pdm.lock ./backend/

# Copy the built Rust wheel from the 'rust_builder' stage.
# The wheel will be copied to './backend/wheels/' within this image.
# We copy the entire directory as the exact wheel filename is generated at build time.
COPY --from=rust_builder --chown=appuser:appuser /app/rust_engine/target/wheels/ ./backend/wheels/

# Install PDM globally (for the appuser, or rather, accessible by appuser)
# Pinning PDM version for consistency
RUN pip install pdm==2.11.0

# Set PDM_APPL_PATH to the directory containing pyproject.toml.
# This tells PDM where the project root is located for managing its virtual environment.
ENV PDM_APPL_PATH=/app/backend

# Install Python dependencies using PDM.
# PDM will create a virtual environment inside /app/backend/.venv by default.
# --prod: Installs production dependencies.
# --no-self: Prevents PDM from installing the project itself as an editable package.
# --no-editable: Ensures all packages are installed from wheels/archives, not as editable installs.
# --no-sync: Prevents removal of packages not in the lock file (helpful if doing multiple installs).
RUN PDM_APPL_PATH=/app/backend pdm install --prod --no-self --no-editable --no-sync

# Find the Rust wheel file and install it into the created virtual environment.
# This is crucial for PyO3 to link correctly.
# The `ls -1` command will list the wheel file name, and `head -n 1` picks the first one.
# pip will install it into the active virtual environment managed by PDM.
RUN WHEEL_FILE=$(ls -1 /app/backend/wheels/*.whl | head -n 1) && \
    pip install "${WHEEL_FILE}"

# Copy the rest of the application source code into the image.
# This includes all Python modules for FastAPI and Celery workers.
COPY --chown=appuser:appuser backend/src ./backend/src/

# Copy the shell scripts from the infrastructure directory.
# These scripts manage the container's entrypoint and migrations.
COPY --chown=appuser:appuser infrastructure/scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=appuser:appuser infrastructure/scripts/run_migrations.sh /usr/local/bin/run_migrations.sh

# Give execution permissions to the entrypoint scripts.
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/run_migrations.sh

# Set PYTHONPATH to include our source code so Python can find modules like karyaksham_api.
# This is important even with PDM's venv if the venv's site-packages isn't automatically on path.
ENV PYTHONPATH=/app/backend/src

# Set environment variables that specify the main application modules for FastAPI and Celery.
# These are used by the entrypoint.sh script to start the correct service.
ENV APP_MODULE=karyaksham_api.main:app
ENV WORKER_APP_MODULE=karyaksham_workers.celery_app:celery_app

# Define the entrypoint for the container.
# tini ensures proper signal handling, which is critical for graceful shutdowns.
# It passes control to our custom entrypoint.sh script.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]

# Define the default command that will be executed if no command is provided when running the container.
# The 'entrypoint.sh' script will interpret "api" to start the FastAPI server.
# This allows overriding to "worker" for Celery workers.
CMD ["api"]

# Expose the port on which the FastAPI application will listen.
EXPOSE 8000