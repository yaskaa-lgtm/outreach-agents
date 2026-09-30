"""Journal of every LLM call: cost and performance, never the prompt or the answer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, WorkspaceScopedMixin


class LLMCall(IdMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "llm_calls"

    agent: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(100))
    model_role: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(default=0)
    cache_creation_input_tokens: Mapped[int] = mapped_column(default=0)
    cost_eur: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0))
    duration_ms: Mapped[int] = mapped_column(default=0)
    success: Mapped[bool]
    stop_reason: Mapped[str | None] = mapped_column(String(40))
    error_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_llm_calls_workspace_created", "workspace_id", "created_at"),)
