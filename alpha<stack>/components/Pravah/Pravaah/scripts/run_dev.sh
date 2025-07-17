#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory of the script and then navigate to the actual project root.
# This assumes the script is located at 'PROJECT_ROOT/scripts/run_dev.sh'.
script_dir=$(dirname "$0")
project_root=$(cd "$script_dir/.." && pwd)

echo "--- Pravah: High-Performance File & Data Processing Engine (Development Server) ---"
echo "Project root identified: $project_root"

# --- 1. Load Environment Variables ---
# Source the .env file from the project root if it exists.
# `set -a` automatically exports variables, `set +a` disables this after sourcing.
set -a
if [ -f "$project_root/.env" ]; then
    echo "Loading environment variables from $project_root/.env..."
    source "$project_root/.env"
else
    echo "Warning: .env file not found at $project_root/.env. " \
         "Ensure necessary environment variables (e.g., DATABASE_URL, LOG_LEVEL) are set manually."
fi
set +a

# Set default Uvicorn host and port if not specified in .env
UVICORN_HOST=${UVICORN_HOST:-0.0.0.0}
UVICORN_PORT=${UVICORN_PORT:-8000}

# --- 2. Build Pravah Rust Core Engine ---
echo "Building Pravah Rust core engine in development mode using maturin..."
# Navigate to the project root and run `maturin develop`.
# This command builds the Rust library (pravah_core) and installs it as a
# Python module into the currently active Python environment in editable mode.
# This ensures Python can import the Rust code directly.
(cd "$project_root" && maturin develop)
if [ $? -ne 0 ]; then
    echo "Error: Failed to build Pravah Rust core. Please check your Rust toolchain setup (rustup) " \
         "and ensure maturin is installed (pip install maturin)."
    exit 1
fi
echo "Pravah Rust core built and installed successfully."

# --- 3. Start FastAPI Application with Uvicorn ---
echo "Starting FastAPI application with Uvicorn and hot-reloading..."
echo "Application will be accessible at: http://$UVICORN_HOST:$UVICORN_PORT"
echo "Press Ctrl+C to stop the server."

# Navigate to the project root and start Uvicorn.
# `app.main:app` specifies the FastAPI application object within app/main.py.
# `--reload` enables hot-reloading for development, automatically restarting on code changes.
(cd "$project_root" && uvicorn app.main:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" --reload)

echo "Pravah development server stopped."