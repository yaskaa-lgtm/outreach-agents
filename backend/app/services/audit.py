"""Audit trail helper. `details` must never contain secrets or email bodies."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def record(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    action: str,
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Adds an entry to the current transaction (committed with the change it describes)."""
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_type="user" if actor_id else "system",
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )
