from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import Connection

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# We need to import our application settings to get the database URL
from config.settings import settings

# Add your model's MetaData object here for 'autogenerate' support.
# It is crucial to import all model modules here so that their table
# definitions are registered with the Base.metadata object before migrations run.
from app.db.models.base import Base
import app.db.models.job  # noqa: F401 - Imported for side effect of registering models
import app.db.models.user # noqa: F401 - Imported for side effect of registering models

target_metadata = Base.metadata

# The database URL should be loaded from our application settings (environment variables)
# for production environments, rather than directly from alembic.ini.
database_url = settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an actual DBAPI connection.
    Having a connection in hand is typically not needed in offline mode.
    """
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        # Get general sqlalchemy options from alembic.ini, but override URL
        # with our dynamically loaded one from application settings.
        config.get_section_arg(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=database_url, # Explicitly pass the URL from application settings
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()