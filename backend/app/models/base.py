"""Declarative base and shared column helpers.

Conventions: UUID primary keys, UTC `timestamptz` timestamps, and a `workspace_id` on every
business table so the schema is multi-tenant from day one.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Deterministic constraint names: Alembic migrations stay readable and reproducible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012 (SQLAlchemy reads this class attribute)
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
        list[str]: JSONB,
    }
    # Values computed by PostgreSQL (created_at, updated_at...) come back with INSERT/UPDATE
    # ... RETURNING, so objects stay fully readable after commit (no lazy load in async code).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkspaceScopedMixin:
    @declared_attr
    def workspace_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
