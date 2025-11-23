"""
Alembic environment configuration for db-common-models.

This module configures the Alembic migration environment, setting up database
connections, SQLAlchemy metadata, and defining how migrations are executed in
both offline (SQL script generation) and online (direct database execution) modes.

The configuration imports all model metadata from db_common_models.models to enable
Alembic's auto-generation capabilities for detecting schema changes across all models
including the new Figma integration tables (FigmaInstallation, FigmaInstallationAccess,
FigmaAttachment).

Modes:
    Offline: Generates SQL scripts without database connection (--sql flag)
    Online: Executes migrations directly against the database
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
import os

# Add parent directory to path to enable importing db_common_models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Alembic Config object provides access to alembic.ini values
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and all models to register metadata for auto-generation
# This ensures Alembic can detect schema changes across all tables
from models import Base, FigmaInstallation, FigmaInstallationAccess, FigmaAttachment

# Set target metadata for Alembic to use when generating migrations
# This metadata contains all table definitions from registered models
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we don't
    even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    This mode is useful for generating SQL scripts that can be reviewed before
    execution or applied in environments where direct database access is restricted.

    Usage:
        alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include schemas if needed for multi-schema databases
        # include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context. This mode directly executes migrations against the
    configured database.

    The engine is configured with NullPool to prevent connection pooling,
    which is appropriate for migration scripts that run as one-off processes.

    Usage:
        alembic upgrade head
    """
    # Create engine with configuration from alembic.ini
    # NullPool prevents connection pooling since migrations are one-off operations
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Enable compare_type to detect column type changes
            compare_type=True,
            # Enable compare_server_default to detect default value changes
            # compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Determine which mode to run based on Alembic context
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
