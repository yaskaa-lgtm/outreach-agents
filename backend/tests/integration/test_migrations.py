"""Migrations go up and down cleanly, and the models match the latest migration."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.core.config import Settings
from app.models import Base

pytestmark = pytest.mark.integration


def test_upgrade_downgrade_upgrade(
    migrations: tuple[Callable[[str, str], str], Callable[[str], Config]],
) -> None:
    recreate_database, alembic_config = migrations
    url = recreate_database(Settings(_env_file=None).database_url, "_migrations_test")
    config = alembic_config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_models_and_migrations_are_in_sync(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    finally:
        engine.dispose()
    assert differences == [], "run: alembic revision --autogenerate -m '...'"
