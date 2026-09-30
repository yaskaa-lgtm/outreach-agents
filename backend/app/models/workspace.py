"""Tenancy and authentication tables: workspaces, users, user sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, WorkspaceScopedMixin


class Workspace(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200))
    daily_llm_budget_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    __table_args__ = (CheckConstraint("daily_llm_budget_eur > 0", name="budget_positive"),)


class User(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    is_demo: Mapped[bool] = mapped_column(default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("role IN ('owner')", name="role"),)


class UserSession(IdMixin, WorkspaceScopedMixin, Base):
    """Server-side session. The cookie holds a random token; only its hash is stored."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
