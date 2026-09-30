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


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Build Settings without reading `.env`; keyword arguments override fields."""

    def _make(**overrides: Any) -> Settings:
        return Settings(_env_file=None, **overrides)

    return _make
