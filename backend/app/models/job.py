"""Background work: the PostgreSQL job queue and the cache/journal of data-provider calls."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, WorkspaceScopedMixin


class Job(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """One unit of background work. Picked with `FOR UPDATE SKIP LOCKED`; handlers are
    idempotent, so a job can safely run again after a crash."""

    __tablename__ = "jobs"

    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Groups the jobs of one campaign (progress display).
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(100))
    last_error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'dead')",
            name="status",
        ),
        Index("ix_jobs_pick", "status", "run_after"),
    )


class ProviderCall(IdMixin, WorkspaceScopedMixin, Base):
    """Journal and cache of paid or rate-limited data-provider calls (never the API key)."""

    __tablename__ = "provider_calls"

    provider: Mapped[str] = mapped_column(String(30))
    operation: Mapped[str] = mapped_column(String(50))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int]
    response: Mapped[dict[str, Any] | None] = mapped_column()
    credits_used: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_provider_calls_lookup", "provider", "operation", "request_hash"),
        Index("ix_provider_calls_workspace_created", "workspace_id", "created_at"),
    )
