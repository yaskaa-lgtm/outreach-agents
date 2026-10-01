"""PostgreSQL job queue (no Redis in the MVP).

- `enqueue` is idempotent: a second job with the same `idempotency_key` is ignored.
- `claim_next` takes one due job with `SELECT ... FOR UPDATE SKIP LOCKED`, so several workers
  never take the same job and never wait for each other.
- Failures are retried with exponential backoff, then the job is marked `dead`.
- `postpone` pauses a job without counting an attempt (e.g. LLM budget reached until tomorrow).
- `requeue_stale` gives back jobs whose worker crashed while running them.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job

BASE_DELAY_SECONDS = 10
MAX_DELAY_SECONDS = 3600


def utc_now() -> datetime:
    return datetime.now(UTC)


async def enqueue(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    kind: str,
    payload: dict[str, Any],
    idempotency_key: str,
    correlation_id: uuid.UUID | None = None,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> None:
    statement = (
        insert(Job)
        .values(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            kind=kind,
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            run_after=run_after or utc_now(),
            max_attempts=max_attempts,
            status="queued",
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
    )
    await db.execute(statement)


async def claim_next(db: AsyncSession, worker_id: str) -> Job | None:
    job = await db.scalar(
        select(Job)
        .where(Job.status == "queued", Job.run_after <= utc_now())
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = "running"
    job.locked_at = utc_now()
    job.locked_by = worker_id
    job.attempts += 1
    await db.commit()
    return job


def backoff(attempts: int) -> timedelta:
    delay = min(BASE_DELAY_SECONDS * 2 ** max(attempts - 1, 0), MAX_DELAY_SECONDS)
    return timedelta(seconds=delay + random.uniform(0, delay / 10))  # noqa: S311 (jitter)


async def mark_succeeded(db: AsyncSession, job_id: uuid.UUID) -> None:
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="succeeded", locked_at=None, last_error=None)
    )
    await db.commit()


async def mark_failed(db: AsyncSession, job_id: uuid.UUID, error: str) -> str:
    job = await db.get(Job, job_id)
    if job is None:
        return "missing"
    job.last_error = error[:1000]
    job.locked_at = None
    if job.attempts >= job.max_attempts:
        job.status = "dead"
    else:
        job.status = "queued"
        job.run_after = utc_now() + backoff(job.attempts)
    await db.commit()
    return job.status


async def postpone(db: AsyncSession, job_id: uuid.UUID, until: datetime, reason: str) -> None:
    job = await db.get(Job, job_id)
    if job is None:
        return
    job.status = "queued"
    job.run_after = until
    job.locked_at = None
    job.attempts = max(job.attempts - 1, 0)
    job.last_error = reason[:1000]
    await db.commit()


async def requeue_stale(db: AsyncSession, older_than: timedelta) -> int:
    result = await db.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < utc_now() - older_than)
        .values(status="queued", locked_at=None, locked_by=None)
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
