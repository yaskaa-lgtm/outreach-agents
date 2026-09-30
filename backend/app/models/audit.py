"""Audit trail: who did what, when. No secrets and no email bodies in `details`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, WorkspaceScopedMixin


class AuditLog(IdMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "audit_log"

    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None]
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (CheckConstraint("actor_type IN ('user', 'system')", name="actor_type"),)
