"""Background worker entry point: `uv run python -m app.worker`.

Phase 0 stub: it checks the database connection and idles. The PostgreSQL job queue
(`SELECT ... FOR UPDATE SKIP LOCKED`) arrives in Phase 2.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys

from app.core.config import get_settings
from app.core.database import create_engine, ping_database
from app.core.logging import configure_logging

logger = logging.getLogger("app.worker")


async def run_worker(stop: asyncio.Event) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        database_ok = await ping_database(engine)
        logger.info(
            "Worker started in %s mode (database: %s). No job kinds registered yet.",
            settings.mode,
            "ok" if database_ok else "unavailable",
        )
        while not stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
    finally:
        await engine.dispose()
        logger.info("Worker stopped")


async def main() -> None:
    configure_logging(get_settings().log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        # Not available on Windows: Ctrl+C then raises KeyboardInterrupt instead.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    await run_worker(stop)


if __name__ == "__main__":
    # psycopg's async mode does not support Windows' default ProactorEventLoop.
    # https://www.psycopg.org/psycopg3/docs/advanced/async.html
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main(), loop_factory=loop_factory)
