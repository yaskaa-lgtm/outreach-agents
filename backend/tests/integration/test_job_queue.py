"""PostgreSQL job queue: idempotent enqueue, SKIP LOCKED claim, retries, dead jobs, pause."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import LLMBudgetExhaustedError
from app.models import Job
from app.worker import queue
from app.worker.runner import Handler, run_once

pytestmark = pytest.mark.integration

Maker = async_sessionmaker[AsyncSession]


async def _enqueue(
    sessionmaker: Maker,
    workspace_id: uuid.UUID,
    key: str,
    kind: str = "test",
    max_attempts: int = 3,
) -> None:
    async with sessionmaker() as db:
        await queue.enqueue(
            db,
            workspace_id=workspace_id,
            kind=kind,
            payload={"n": 1},
            idempotency_key=key,
            max_attempts=max_attempts,
        )
        await db.commit()


async def _only_job(sessionmaker: Maker) -> Job:
    async with sessionmaker() as db:
        job = await db.scalar(select(Job))
        assert job is not None
        return job


async def test_enqueue_is_idempotent(sessionmaker: Maker, workspace_id: uuid.UUID) -> None:
    await _enqueue(sessionmaker, workspace_id, "same-key")
    await _enqueue(sessionmaker, workspace_id, "same-key")
    async with sessionmaker() as db:
        assert len(list(await db.scalars(select(Job)))) == 1


async def test_a_locked_job_is_skipped_by_other_workers(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    await _enqueue(sessionmaker, workspace_id, "k1")
    async with sessionmaker() as first, sessionmaker() as second:
        # Hold the row lock in an open transaction, like a worker in the middle of a claim.
        locked = await first.scalar(select(Job).with_for_update())
        assert locked is not None
        assert await queue.claim_next(second, "worker-b") is None
        await first.rollback()
        claimed = await queue.claim_next(second, "worker-b")
        assert claimed is not None
        assert (claimed.status, claimed.attempts, claimed.locked_by) == ("running", 1, "worker-b")
        assert await queue.claim_next(first, "worker-a") is None  # running: never given twice


async def test_failures_are_retried_with_backoff_then_dead(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    await _enqueue(sessionmaker, workspace_id, "k2", max_attempts=2)
    async with sessionmaker() as db:
        job = await queue.claim_next(db, "w")
        assert job is not None
        assert await queue.mark_failed(db, job.id, "boom") == "queued"
    retried = await _only_job(sessionmaker)
    assert retried.run_after > datetime.now(UTC) + timedelta(seconds=5)

    async with sessionmaker() as db:
        await db.execute(update(Job).values(run_after=datetime.now(UTC)))
        await db.commit()
        job = await queue.claim_next(db, "w")
        assert job is not None
        assert await queue.mark_failed(db, job.id, "boom again") == "dead"
    assert (await _only_job(sessionmaker)).last_error == "boom again"


async def test_postpone_does_not_count_an_attempt(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    await _enqueue(sessionmaker, workspace_id, "k3")
    async with sessionmaker() as db:
        job = await queue.claim_next(db, "w")
        assert job is not None
        await queue.postpone(db, job.id, datetime.now(UTC) + timedelta(hours=1), "budget")
    paused = await _only_job(sessionmaker)
    assert (paused.status, paused.attempts) == ("queued", 0)
    async with sessionmaker() as db:
        assert await queue.claim_next(db, "w") is None  # not due before the new date


async def test_stale_running_jobs_are_requeued(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    await _enqueue(sessionmaker, workspace_id, "k4")
    async with sessionmaker() as db:
        await queue.claim_next(db, "crashed-worker")
        assert await queue.requeue_stale(db, timedelta(minutes=15)) == 0  # still fresh
        await db.execute(update(Job).values(locked_at=datetime.now(UTC) - timedelta(hours=1)))
        await db.commit()
        assert await queue.requeue_stale(db, timedelta(minutes=15)) == 1
    assert (await _only_job(sessionmaker)).status == "queued"


async def test_runner_records_success_failure_unknown_kind_and_budget_pause(
    sessionmaker: Maker, workspace_id: uuid.UUID, make_settings: Callable[..., Settings]
) -> None:
    calls: list[dict[str, Any]] = []
    resets_at = (datetime.now(UTC) + timedelta(hours=3)).replace(microsecond=0)

    async def ok(
        _settings: Settings, _maker: Maker, _ws: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        calls.append(payload)

    async def broken(*_args: Any) -> None:
        raise RuntimeError("handler failed")

    async def over_budget(*_args: Any) -> None:
        raise LLMBudgetExhaustedError("paused", resets_at=resets_at.isoformat())

    handlers: dict[str, Handler] = {"ok": ok, "broken": broken, "budget": over_budget}
    for kind in (*handlers, "unknown"):
        await _enqueue(sessionmaker, workspace_id, f"run-{kind}", kind=kind)

    settings = make_settings()
    while await run_once(settings, sessionmaker, "w", handlers):
        pass

    async with sessionmaker() as db:
        jobs = {job.kind: job for job in await db.scalars(select(Job))}
    assert calls == [{"n": 1}]
    assert jobs["ok"].status == "succeeded"
    assert jobs["broken"].status == "queued"
    assert jobs["broken"].last_error == "RuntimeError: handler failed"
    assert (jobs["budget"].status, jobs["budget"].attempts) == ("queued", 0)
    assert jobs["budget"].run_after == resets_at
    assert jobs["unknown"].last_error == "Unknown job kind 'unknown'"
