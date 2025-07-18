#!/bin/sh
set -e

# Script to run database migrations using Alembic for the Karyaksham project.
# It ensures the PostgreSQL database is reachable before attempting to apply migrations.

# --- Configuration ---
# These environment variables are expected to be set in the deployment environment
# (e.g., Docker Compose, Kubernetes secrets, or injected from a .env file locally).
# Default values are provided for development convenience.
DB_HOST="${POSTGRES_SERVER:-db}"
DB_USER="${POSTGRES_USER:-karyaksham}"
DB_PASSWORD="${POSTGRES_PASSWORD:-password}"
DB_NAME="${POSTGRES_DB:-karyakshamdb}"
DB_PORT="${POSTGRES_PORT:-5432}"

# Relative path to the Alembic migrations directory from this script's location.
# Script location: karyaksham/infrastructure/scripts/run_migrations.sh
# Alembic root:    karyaksham/backend/src/karyaksham_api/db/migrations/
ALEMBIC_MIGRATIONS_DIR="../../backend/src/karyaksham_api/db/migrations"

MAX_DB_WAIT_RETRIES=15
DB_WAIT_INTERVAL_SECONDS=2

# --- Functions ---

# Function to check if a command exists in the PATH.
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Main Logic ---

echo "Starting Karyaksham database migration process..."

# 1. Validate required commands are available in the environment.
if ! command_exists psql; then
    echo "Error: 'psql' command not found. Please ensure PostgreSQL client tools are installed in the container/environment."
    exit 1
fi

if ! command_exists alembic; then
    echo "Error: 'alembic' command not found. Please ensure Alembic is installed in the Python environment and accessible in PATH."
    exit 1
fi

# 2. Wait for the PostgreSQL database to become available.
echo "Attempting to connect to PostgreSQL at ${DB_HOST}:${DB_PORT} for database '${DB_NAME}' as user '${DB_USER}'..."
for i in $(seq 1 ${MAX_DB_WAIT_RETRIES}); do
    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c '\q'; then
        echo "PostgreSQL is ready."
        break
    else
        echo "PostgreSQL is not yet available. Retrying in ${DB_WAIT_INTERVAL_SECONDS} seconds... (Attempt ${i}/${MAX_DB_WAIT_RETRIES})"
        sleep ${DB_WAIT_INTERVAL_SECONDS}
    fi

    if [ ${i} -eq ${MAX_DB_WAIT_RETRIES} ]; then
        echo "Error: PostgreSQL did not become ready within the maximum allowed time (${MAX_DB_WAIT_RETRIES} retries). Exiting."
        exit 1
    fi
done

# 3. Export the DATABASE_URL environment variable.
# This variable is typically read by Alembic's env.py script to establish the database connection.
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "DATABASE_URL environment variable set for Alembic migrations."

# 4. Navigate to the Alembic migrations directory.
# Changing to this directory ensures Alembic can find its configuration file (alembic.ini)
# and the migration scripts (in the 'versions' subdirectory) correctly.
if [ ! -d "${ALEMBIC_MIGRATIONS_DIR}" ]; then
    echo "Error: Alembic migrations directory not found at the expected path: '${ALEMBIC_MIGRATIONS_DIR}' relative to this script."
    exit 1
fi

echo "Navigating to Alembic migrations directory: ${ALEMBIC_MIGRATIONS_DIR}"
cd "${ALEMBIC_MIGRATIONS_DIR}"

# 5. Execute the database migrations.
# 'alembic upgrade head' applies all pending migrations up to the latest version.
echo "Executing Alembic 'upgrade head' to apply all pending migrations..."
alembic upgrade head

echo "Database migrations completed successfully."

# The script will exit with status 0 upon successful completion.
# In a containerized environment, this script typically runs as a pre-start hook
# or as the sole command in a dedicated migration container, then exits.