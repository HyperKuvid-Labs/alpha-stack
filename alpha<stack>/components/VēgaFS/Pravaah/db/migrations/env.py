import logging
import os
import sys
from pathlib import Path

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Set up logging for Alembic.
# This reads section 'alembic' from alembic.ini if available.
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Add the application's source directory to sys.path.
# This allows Alembic to import application models.
#
# Assumptions:
# - The project root is `VēgaFS/` (the directory containing `app/`, `rust_core/`, `Pravaah/`).
# - The main Python application source code is located in `VēgaFS/app/`.
# - This `env.py` file is located at `VēgaFS/Pravaah/db/migrations/env.py`.
# - Database models are defined within the `app` package, e.g., in `VēgaFS/app/db/models/base.py`.
#
# Navigate from `env.py`'s directory to the project root, then to the `app/` directory.
current_file_dir = Path(__file__).parent               # .../VēgaFS/Pravaah/db/migrations
db_dir = current_file_dir.parent                       # .../VēgaFS/Pravaah/db
pravaah_dir = db_dir.parent                            # .../VēgaFS/Pravaah
project_root = pravaah_dir.parent                      # .../VēgaFS
app_source_dir = project_root / "app"                  # .../VēgaFS/app

sys.path.insert(0, str(app_source_dir))

# Import the Base.metadata from your application's models.
# Since `VēgaFS/app/` is added to sys.path, Python can find the `db` module directly.
try:
    from db.models.base import Base
    target_metadata = Base.metadata
    logging.info("Successfully imported application models metadata (Base.metadata).")
except ImportError as e:
    logging.error(f"Failed to import application models from 'db.models.base': {e}")
    logging.error("Please ensure the 'db/models/base.py' module exists within the 'app' directory "
                  "and that 'VēgaFS/app/' is correctly added to sys.path.")
    # Set target_metadata to None and optionally raise an error to halt migrations.
    # Migrations cannot proceed without the application's schema definition.
    target_metadata = None
    raise RuntimeError("Cannot proceed without application models metadata.") from e

# Get the database URL from environment variables,
# overriding any setting in alembic.ini for robust production configuration.
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
else:
    logging.warning("DATABASE_URL environment variable not set. "
                    "Alembic will attempt to use 'sqlalchemy.url' from alembic.ini.")

def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    By skipping the Engine creation, we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario, we need to create an Engine and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # For PostgreSQL, especially with JSONB or other custom types,
            # it is crucial to enable type comparison to ensure Alembic
            # accurately detects changes in column types.
            compare_type=True,
            # Optionally, enable `render_as_batch=True` for batch migrations
            # if you anticipate operations (e.g., column renaming, type changes)
            # that require a "move table" strategy for non-blocking DDL.
            # render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# Determine whether to run migrations in offline or online mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()