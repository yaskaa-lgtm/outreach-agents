"""Checks against a real PostgreSQL (start it with `docker compose up -d db`).

Skipped locally when the database is not running; CI sets REQUIRE_DATABASE=1 so that a
missing database is a failure there, never a silent skip.
"""

from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.core.database import create_engine, ping_database

pytestmark = pytest.mark.integration


async def test_database_answers_select_one() -> None:
    engine = create_engine(Settings().database_url)
    try:
        reachable = await ping_database(engine, timeout_seconds=5)
    finally:
        await engine.dispose()

    if not reachable and not os.environ.get("REQUIRE_DATABASE"):
        pytest.skip("PostgreSQL not reachable: run `docker compose up -d db` first")
    assert reachable
