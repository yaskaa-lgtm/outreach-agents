"""Database engine helpers (SQLAlchemy 2, async, psycopg 3 driver)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


def create_engine(database_url: str) -> AsyncEngine:
    """Create the async engine. `pool_pre_ping` drops dead connections transparently."""
    return create_async_engine(database_url, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit (no implicit reload).
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping_database(engine: AsyncEngine, timeout_seconds: float = 2.0) -> bool:
    """Return True if the database answers `SELECT 1` within the timeout."""
    try:
        async with asyncio.timeout(timeout_seconds), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # any failure means "not reachable" for a health check
        # Only the exception type: the message may contain the connection string.
        logger.warning("Database ping failed: %s", type(exc).__name__)
        return False
    return True
