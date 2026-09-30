"""Shared test fixtures.

Tests never read the developer's `.env` file: settings are built explicitly.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import Any

import pytest

from app.core.config import Settings

if sys.platform == "win32":
    # psycopg's async mode does not support Windows' default ProactorEventLoop.
    # https://www.psycopg.org/psycopg3/docs/advanced/async.html
    def pytest_asyncio_loop_factories(
        config: pytest.Config, item: pytest.Item
    ) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
        return {"selector": asyncio.SelectorEventLoop}


# Variables of the developer's shell that must not leak into tests (DATABASE_URL is kept:
# CI uses it to point the integration tests at its PostgreSQL service).
_ISOLATED_ENV_VARS = (
    "DEMO_MODE",
    "DRY_RUN",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "ANTHROPIC_API_KEY",
    "LLM_MODEL_REASONING",
    "LLM_MODEL_FAST",
    "LLM_EFFORT_REASONING",
    "LLM_PRICE_REASONING_INPUT_USD_PER_MTOK",
    "LLM_PRICE_REASONING_OUTPUT_USD_PER_MTOK",
    "LLM_PRICE_FAST_INPUT_USD_PER_MTOK",
    "LLM_PRICE_FAST_OUTPUT_USD_PER_MTOK",
    "USD_TO_EUR_RATE",
    "HUNTER_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Build Settings without reading `.env`; keyword arguments override fields."""

    def _make(**overrides: Any) -> Settings:
        return Settings(_env_file=None, **overrides)

    return _make
