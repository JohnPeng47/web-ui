import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, engine_from_config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object
config = context.config

# Make sure Python can import from the cnc directory
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import after setting sys.path
from sqlmodel import SQLModel

# Import all models to ensure they're registered with SQLModel metadata
from cnc.database.models import *
from cnc.database.agent.models import *

# Import your database URL
from cnc.database.session import DATABASE_URL

# Convert async URL to sync URL for Alembic
sync_DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite:", "sqlite:")

# Set the SQLAlchemy URL
config.set_main_option("sqlalchemy.url", sync_DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata
target_metadata = SQLModel.metadata

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

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Use the sync version of the URL
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        connectable = engine_from_config(
            context.config.get_section(context.config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()