"""Discovery tables (Phase 2): campaigns, companies, contacts, prospects and their history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, WorkspaceScopedMixin
from app.orchestrator.states import PROSPECT_STATES

_STATE_LIST = ", ".join(f"'{state}'" for state in PROSPECT_STATES)


class Campaign(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "campaigns"

    offer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offer_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    target_country: Mapped[str] = mapped_column(String(2), default="FR")
    companies_per_segment: Mapped[int]

    __table_args__ = (CheckConstraint("target_country = 'FR'", name="france_only"),)


class CampaignSegment(WorkspaceScopedMixin, Base):
    __tablename__ = "campaign_segments"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"), primary_key=True
    )


class Company(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "companies"

    siren: Mapped[str | None] = mapped_column(String(9))
    name: Mapped[str] = mapped_column(String(300))
    naf_code: Mapped[str | None] = mapped_column(String(6))
    headcount_range: Mapped[str | None] = mapped_column(String(2))
    postal_code: Mapped[str | None] = mapped_column(String(5))
    city: Mapped[str | None] = mapped_column(String(200))
    departement: Mapped[str | None] = mapped_column(String(3))
    is_sole_trader: Mapped[bool] = mapped_column(default=False)
    # A domain is never invented: it comes from a source and is confirmed by the SIREN.
    website_domain: Mapped[str | None] = mapped_column(String(253))
    domain_source: Mapped[str | None] = mapped_column(String(20))
    domain_status: Mapped[str] = mapped_column(String(20), default="unknown")
    domain_evidence_url: Mapped[str | None] = mapped_column(String(2048))
    # Officers from the official registry: first names, last name and role only.
    officers: Mapped[list[Any]] = mapped_column(default=list)
    source_provider: Mapped[str] = mapped_column(String(20))

    __table_args__ = (
        CheckConstraint(
            "domain_status IN ('unknown', 'confirmed', 'unconfirmed', 'not_found')",
            name="domain_status",
        ),
        Index(
            "uq_companies_workspace_siren",
            "workspace_id",
            "siren",
            unique=True,
            postgresql_where=text("siren IS NOT NULL"),
        ),
        Index(
            "uq_companies_workspace_domain",
            "workspace_id",
            "website_domain",
            unique=True,
            postgresql_where=text("website_domain IS NOT NULL"),
        ),
    )


class Contact(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    # SHA-256 of the normalised address: used for de-duplication and, later, suppression.
    email_hash: Mapped[str | None] = mapped_column(String(64))
    is_generic: Mapped[bool] = mapped_column(default=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_provider: Mapped[str] = mapped_column(String(20))
    source_url: Mapped[str | None] = mapped_column(String(2048))

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified', 'valid', 'accept_all', 'unknown', "
            "'invalid', 'webmail', 'disposable')",
            name="verification_status",
        ),
        Index(
            "uq_contacts_workspace_email_hash",
            "workspace_id",
            "email_hash",
            unique=True,
            postgresql_where=text("email_hash IS NOT NULL"),
        ),
    )


class Prospect(IdMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """One company inside one campaign, moved forward by the state machine."""

    __tablename__ = "prospects"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("segments.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    state: Mapped[str] = mapped_column(String(30), default="discovered")
    state_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("campaign_id", "company_id", name="uq_prospects_campaign_company"),
        CheckConstraint(f"state IN ({_STATE_LIST})", name="state"),
    )


class ProspectTransition(IdMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "prospect_transitions"

    prospect_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True
    )
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
