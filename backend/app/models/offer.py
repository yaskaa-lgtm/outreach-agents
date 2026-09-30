"""What the client sells (Agent 1 output) and who needs it (Agent 2 output)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, WorkspaceScopedMixin


class OfferProfile(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "offer_profiles"

    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_description: Mapped[str | None] = mapped_column(Text)
    # Validated `OfferProfileData` (app.schemas.offer); every claim carries its source.
    data: Mapped[dict[str, Any]]
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # Claims removed because their excerpt was not found in the fetched pages.
    warnings: Mapped[list[str]] = mapped_column(default=list)
    pages_fetched: Mapped[list[str]] = mapped_column(default=list)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("status IN ('draft', 'validated')", name="status"),)


class Segment(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "segments"

    offer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offer_profiles.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    # NAF codes, headcount ranges, départements, keywords (app.schemas.segment).
    criteria: Mapped[dict[str, Any]]
    target_titles: Mapped[list[str]]
    main_pain: Mapped[str] = mapped_column(Text)
    hook_angle: Mapped[str] = mapped_column(Text)
    fit_score: Mapped[int]
    fit_rationale: Mapped[str] = mapped_column(Text)
    selected: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (CheckConstraint("fit_score BETWEEN 0 AND 100", name="fit_score_range"),)
