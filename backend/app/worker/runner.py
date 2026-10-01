"""The worker loop: take one due job, run its handler, record the outcome."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import LLMBudgetExhaustedError
from app.discovery.pipeline import build_providers, discover_companies, process_prospect
from app.worker import queue

logger = logging.getLogger("app.worker")

STALE_AFTER = timedelta(minutes=15)

Handler = Callable[
    [Settings, async_sessionmaker[AsyncSession], uuid.UUID, dict[str, Any]], Awaitable[Any]
]


async def _discover(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    payload: dict[str, Any],
) -> Any:
    providers = build_providers(settings, sessionmaker, workspace_id)
    try:
        return await discover_companies(sessionmaker, providers, payload)
    finally:
        await providers.aclose()


async def _process(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    payload: dict[str, Any],
) -> Any:
    providers = build_providers(settings, sessionmaker, workspace_id)
    try:
        return await process_prospect(sessionmaker, providers, settings, payload)
    finally:
        await providers.aclose()


HANDLERS: dict[str, Handler] = {
    "discover_companies": _discover,
    "process_prospect": _process,
}


def worker_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


async def run_once(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    worker: str,
    handlers: dict[str, Handler] | None = None,
) -> bool:
    """Run at most one job. Returns False when nothing was due."""
    handlers = handlers or HANDLERS
    async with sessionmaker() as db:
        job = await queue.claim_next(db, worker)
        if job is None:
            return False
        job_id, kind, payload, workspace_id = job.id, job.kind, dict(job.payload), job.workspace_id

    handler = handlers.get(kind)
    async with sessionmaker() as db:
        if handler is None:
            await queue.mark_failed(db, job_id, f"Unknown job kind '{kind}'")
            return True
        try:
            await handler(settings, sessionmaker, workspace_id, payload)
        except LLMBudgetExhaustedError as exc:
            resets_at = datetime.fromisoformat(str(exc.details["resets_at"]))
            await queue.postpone(db, job_id, resets_at, "LLM budget reached: paused until reset")
            logger.info("Job %s paused until the LLM budget resets", kind)
        except Exception as exc:  # any failure is recorded on the job, never crashes the loop
            status = await queue.mark_failed(db, job_id, f"{type(exc).__name__}: {exc}")
            logger.warning("Job %s failed (%s), now %s", kind, type(exc).__name__, status)
        else:
            await queue.mark_succeeded(db, job_id)
    return True


async def run_loop(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], stop: asyncio.Event
) -> None:
    worker = worker_id()
    try:
        async with sessionmaker() as db:
            requeued = await queue.requeue_stale(db, STALE_AFTER)
        if requeued:
            logger.info("Requeued %d jobs left running by a stopped worker", requeued)
    except Exception as exc:  # database not ready yet: the loop below keeps retrying
        logger.warning("Could not check stale jobs (%s)", type(exc).__name__)
    while not stop.is_set():
        try:
            did_work = await run_once(settings, sessionmaker, worker)
        except Exception as exc:  # database down, etc.: wait and retry
            logger.warning("Worker loop error (%s)", type(exc).__name__)
            did_work = False
        if not did_work:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
