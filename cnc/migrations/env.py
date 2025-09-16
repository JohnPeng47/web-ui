import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, engine_from_config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object
config = context.config

# Make sure Python can import from the cnc directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import after setting sys.path
from sqlmodel import SQLModel

# Import all models to ensure they're registered with SQLModel metadata
from cnc.database.models import *
from cnc.database.agent.models import *

# Import your database URL
from cnc.database.session import DATABASE_URL

def get_url():
    """Resolve the SQLAlchemy URL for Alembic based on CLI args or env vars.

    Preference order:
    1) -x env=<section> passed via Alembic CLI
    2) ALEMBIC_ENV or ALEMBIC_SCHEMA environment variables
    3) Fall back to application's DATABASE_URL (converted to sync driver)
    """
    # 1) Check Alembic -x arguments (e.g., `alembic -x env=testing upgrade head`)
    try:
        x_args = context.get_x_argument(as_dictionary=True)
    except Exception:
        x_args = {}

    selected_env = (
        x_args.get("env")
        or os.getenv("ALEMBIC_ENV")
        or os.getenv("ALEMBIC_SCHEMA")  # backward compatibility with previous name
    )

    if selected_env:
        # Try to read URL from the corresponding section in alembic.ini
        try:
            section_url = config.get_section_option(selected_env, "sqlalchemy.url")
            if section_url:
                # Clean up the URL - remove any comments and whitespace
                section_url = section_url.split('#')[0].strip()
                # Convert async to sync URL
                sync_url = section_url.replace("sqlite+aiosqlite:", "sqlite:")
                # Convert relative paths to absolute paths in a robust way
                if sync_url.startswith("sqlite:///./"):
                    # Directories
                    ini_dir = os.path.abspath(os.path.dirname(config.config_file_name)) if config.config_file_name else os.path.abspath(os.getcwd())
                    project_root = os.path.abspath(os.path.dirname(ini_dir))

                    # Extract the relative path part and normalize
                    rel_path = sync_url.replace("sqlite:///./", "").strip()
                    rel_path_norm = rel_path.replace("\\", "/")

                    # If rel path already includes 'cnc/', use project root to avoid 'cnc/cnc'
                    base_dir = project_root if rel_path_norm.startswith("cnc/") else ini_dir

                    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
                    # Normalize to forward slashes for SQLite URLs
                    abs_path_url = abs_path.replace("\\", "/")
                    sync_url = f"sqlite:///{abs_path_url}"
                return sync_url
        except Exception as e:
            print(f"Error reading section {selected_env}: {e}")
            # If the section doesn't exist or has no url, fall through to DATABASE_URL
            pass

    # 3) Default: Convert the app's async DATABASE_URL to sync for Alembic
    default_url = DATABASE_URL.replace("sqlite+aiosqlite:", "sqlite:")
    if default_url.startswith("sqlite:///./"):
        # Convert relative to absolute for default URL too
        ini_dir = os.path.abspath(os.path.dirname(config.config_file_name)) if config.config_file_name else os.path.abspath(os.getcwd())
        project_root = os.path.abspath(os.path.dirname(ini_dir))
        rel_path = default_url.replace("sqlite:///./", "").strip()
        rel_path_norm = rel_path.replace("\\", "/")
        base_dir = project_root if rel_path_norm.startswith("cnc/") else ini_dir
        abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
        abs_path_url = abs_path.replace("\\", "/")
        default_url = f"sqlite:///{abs_path_url}"
    return default_url

# Set the SQLAlchemy URL based on schema selection
resolved_url = get_url()
print(f"Using database URL: {resolved_url}")
config.set_main_option("sqlalchemy.url", resolved_url)

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