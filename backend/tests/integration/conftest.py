"""Integration fixtures: a real PostgreSQL database and the real FastAPI application.

- A dedicated `<database>_test` database is recreated and migrated with Alembic once per
  session (so every test run also checks the migrations), then emptied after each test.
- Skipped when PostgreSQL is not running locally; CI sets REQUIRE_DATABASE=1 so that a
  missing database is a failure there.
- The app runs in-process through httpx's ASGI transport (no network, works on Windows).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.bootstrap import DEMO_EMAIL, DEMO_PASSWORD
from app.core.config import Settings
from app.core.database import create_engine, create_sessionmaker
from app.main import create_app
from app.models import Base, Workspace
from app.providers.llm.base import LLMClient

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _libpq(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def recreate_database(base_url: str, suffix: str) -> str:
    base = make_url(base_url)
    target = base.set(database=f"{base.database}{suffix}")
    admin = base.set(database="postgres")
    try:
        with psycopg.connect(_libpq(admin), autocommit=True, connect_timeout=3) as connection:
            connection.execute(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)')
            connection.execute(f'CREATE DATABASE "{target.database}"')
    except psycopg.OperationalError:
        if os.environ.get("REQUIRE_DATABASE"):
            raise
        pytest.skip("PostgreSQL not reachable: run `docker compose up -d db` first")
    return target.render_as_string(hide_password=False)


def alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def database_url() -> str:
    url = recreate_database(Settings(_env_file=None).database_url, "_test")
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture
def clean_database(database_url: str) -> Iterator[str]:
    yield database_url
    tables = ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
    with psycopg.connect(_libpq(make_url(database_url)), autocommit=True) as connection:
        connection.execute(f"TRUNCATE {tables} CASCADE")


@pytest.fixture
async def sessionmaker(clean_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(clean_database)
    yield create_sessionmaker(engine)
    await engine.dispose()


@pytest.fixture
async def workspace_id(sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with sessionmaker() as db:
        workspace = Workspace(name="Test", daily_llm_budget_eur=Decimal(2))
        db.add(workspace)
        await db.commit()
        return workspace.id


@pytest.fixture
def db_execute(clean_database: str) -> Callable[..., list[tuple[Any, ...]]]:
    """Run raw SQL against the test database (for assertions and test setup)."""

    def _execute(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with psycopg.connect(_libpq(make_url(clean_database)), autocommit=True) as connection:
            cursor = connection.execute(sql, params)
            return cursor.fetchall() if cursor.description else []

    return _execute


@pytest.fixture
def app_settings(
    clean_database: str, make_settings: Callable[..., Settings]
) -> Callable[..., Settings]:
    def _make(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "database_url": clean_database,
            "demo_mode": True,
            # httpx only sends Secure cookies over https; one test checks the flag itself.
            "session_cookie_secure": False,
        }
        values.update(overrides)
        return make_settings(**values)

    return _make


@asynccontextmanager
async def running_app(
    settings: Settings, llm: LLMClient | None = None
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        if llm is not None:
            app.state.services.llm_factory = lambda: llm
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield app, client


@pytest.fixture
async def demo_client(app_settings: Callable[..., Settings]) -> AsyncIterator[httpx.AsyncClient]:
    async with running_app(app_settings()) as (_app, client):
        yield client


async def login(
    client: httpx.AsyncClient, email: str = DEMO_EMAIL, password: str = DEMO_PASSWORD
) -> httpx.Response:
    return await client.post("/auth/login", json={"email": email, "password": password})


_INSERT_LLM_CALL = (
    "INSERT INTO llm_calls (id, workspace_id, agent, model, model_role, prompt_version, "
    "input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens, "
    "cost_eur, duration_ms, success, created_at) "
    "VALUES (%s, %s, 'offer_analyst', 'm', 'reasoning', 'v', 0, 0, 0, 0, %s, 1, true, %s)"
)


@pytest.fixture
def record_spend(db_execute: Callable[..., list[tuple[Any, ...]]]) -> Callable[..., None]:
    """Insert an LLM call costing `cost_eur` (now, or at `when`) for the only workspace."""

    def _record(cost_eur: float, when: datetime | None = None) -> None:
        workspace_id = db_execute("SELECT id FROM workspaces")[0][0]
        created = when or datetime.now(UTC)
        db_execute(_INSERT_LLM_CALL, (uuid.uuid4(), workspace_id, cost_eur, created))

    return _record


# Helpers exposed as fixtures: test modules cannot import from conftest directly.
@pytest.fixture
def run_app() -> Callable[..., Any]:
    return running_app


@pytest.fixture
def log_in() -> Callable[..., Any]:
    return login


@pytest.fixture
def migrations() -> tuple[Callable[[str, str], str], Callable[[str], Config]]:
    return recreate_database, alembic_config
