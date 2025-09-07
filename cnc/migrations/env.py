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

def get_url():
    """Get URL based on environment or section"""
    # Check for environment variable first
    env_schema = os.getenv('ALEMBIC_SCHEMA')
    if env_schema:
        # Try to get URL from specific section
        try:
            url = config.get_section_option(env_schema, "sqlalchemy.url")
            # Convert async URL to sync URL for Alembic
            return url.replace("sqlite+aiosqlite:", "sqlite:")
        except:
            # Fallback to main section or default
            pass
    
    # Default: Convert your main DATABASE_URL to sync
    sync_DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite:", "sqlite:")
    return sync_DATABASE_URL

# Set the SQLAlchemy URL based on schema selection
config.set_main_option("sqlalchemy.url", get_url())

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata
target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    
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
    # Get the appropriate URL
    url = get_url()
    
    # Use the sync version of the URL
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        # Create engine config with the selected URL
        engine_config = {
            "sqlalchemy.url": url,
            "sqlalchemy.poolclass": pool.NullPool
        }
        
        connectable = engine_from_config(
            engine_config,
            prefix="sqlalchemy.",
        )

    with connectable.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()