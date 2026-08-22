"""
Alembic environment configuration for OminiVoice.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import all models to ensure they are registered with Base.metadata
import app.models.models  # noqa: F401
from app.core.config import settings
from app.models import Base

# This is the Alembic Config object
config = context.config

# Override sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("asyncpg", "psycopg2"))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    def do_run_migrations(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    # Check if a connection was passed via config attributes
    if hasattr(config.attributes, 'get') and config.attributes.get('connection'):
        # Use the provided synchronous connection
        # Ensure we're in a transaction for the migrations
        connection = config.attributes['connection']
        # Check if we're in autocommit mode
        if connection.dialect.isolation_level == 'AUTOCOMMIT':
            # In autocommit mode, we need to explicitly manage the transaction
            do_run_migrations(connection)
        else:
            # Normal case: let the context manager handle the transaction
            do_run_migrations(connection)
    else:
        # Create async engine and run migrations
        connectable = create_async_engine(settings.DATABASE_URL)

        async def run_async_migrations():
            async with connectable.connect() as connection:
                await connection.run_sync(do_run_migrations)
            await connectable.dispose()

        import asyncio
        asyncio.run(run_async_migrations())


def run_migrations() -> None:
    """Main entry point for running migrations."""
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()


if __name__ == "__main__":
    run_migrations()