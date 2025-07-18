#!/bin/bash
set -e

echo "Karyaksham Container Entrypoint Script"

# Path to the database migration script.
# This script is responsible for waiting for the database to be available
# and then applying all pending Alembic migrations.
MIGRATION_SCRIPT="/usr/src/app/infrastructure/scripts/run_migrations.sh"

# Ensure the migration script is executable
if [ ! -f "$MIGRATION_SCRIPT" ]; then
    echo "Error: Migration script not found at $MIGRATION_SCRIPT"
    exit 1
fi
chmod +x "$MIGRATION_SCRIPT"

# Execute the migration script.
# It will handle waiting for the DB and applying migrations.
echo "Running database readiness check and migrations via '$MIGRATION_SCRIPT'..."
"$MIGRATION_SCRIPT"

echo "Database is ready and migrations have been applied (or are up-to-date)."

# Execute the main command passed to the Docker container (CMD in Dockerfile).
# This allows the container to serve different roles (e.g., API server, Celery worker).
echo "Executing main command: '$@'"
exec "$@"