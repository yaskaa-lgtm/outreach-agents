"""Campaigns, prospects and CSV import payloads (screen 3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    segment_ids: list[uuid.UUID] = Field(min_length=1, max_length=6)
    companies_per_segment: int | None = Field(default=None, gt=0)


class JobProgress(BaseModel):
    pending: int
    failed: int


class CampaignRead(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    companies_per_segment: int
    segment_ids: list[uuid.UUID]
    counts: dict[str, int]
    jobs: JobProgress


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    siren: str | None
    naf_code: str | None
    headcount_range: str | None
    city: str | None
    departement: str | None
    is_sole_trader: bool
    website_domain: str | None
    domain_status: str
    domain_evidence_url: str | None
    source_provider: str


class ContactSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    title: str | None
    email: str | None
    is_generic: bool
    verification_status: str
    source_provider: str


class ProspectRow(BaseModel):
    id: uuid.UUID
    state: str
    state_reason: str | None
    segment_id: uuid.UUID | None
    company: CompanySummary
    contact: ContactSummary | None


class TransitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_state: str | None
    to_state: str
    reason: str | None
    actor: str
    created_at: datetime


class ProspectDetail(ProspectRow):
    campaign_id: uuid.UUID
    transitions: list[TransitionRead]


class CsvImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv: str = Field(min_length=1, max_length=1_000_000)


class CsvImportResult(BaseModel):
    imported: int
    already_in_campaign: int
    errors: list[str]
