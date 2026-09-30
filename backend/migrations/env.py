"""Alembic environment: synchronous psycopg connection built from DATABASE_URL."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers every table on the metadata)
from app.core.config import Settings
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    # Keep the application's loggers (and pytest's capture) working after migrations.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    # Tests pass an explicit URL through the Alembic config; otherwise use the settings.
    return config.get_main_option("sqlalchemy.url") or Settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
