"""Ideal customer segments (Agent 2). Criteria are validated against official lists so they
can be sent as-is to the company search API (recherche-entreprises.api.gouv.fr)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.reference_data import departements, naf_codes

# INSEE headcount range codes, identical to app/reference_data/headcount_ranges.json
# (a test checks that both lists match).
HeadcountRange = Literal[
    "NN", "00", "01", "02", "03", "11", "12", "21", "22", "31", "32", "41", "42", "51", "52", "53"
]

_NAF_PATTERN = re.compile(r"^\d{2}\.\d{2}[A-Z]$")


class SegmentCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    naf_codes: list[str] = Field(
        min_length=1,
        max_length=15,
        description="NAF rév. 2 sub-class codes, format '62.01Z'.",
    )
    headcount_ranges: list[HeadcountRange] = Field(
        min_length=1, max_length=8, description="INSEE 'tranche d'effectif salarié' codes."
    )
    departements: list[str] = Field(
        max_length=30, description="French département codes ('75', '2A'); empty = all France."
    )
    keywords: list[str] = Field(max_length=10, description="Short search keywords.")

    @field_validator("naf_codes")
    @classmethod
    def _known_naf_codes(cls, values: list[str]) -> list[str]:
        known = naf_codes()
        cleaned = [value.strip().upper() for value in values]
        unknown = [v for v in cleaned if not _NAF_PATTERN.match(v) or v not in known]
        if unknown:
            raise ValueError(f"Unknown NAF codes: {', '.join(unknown)} (expected e.g. '62.01Z')")
        return list(dict.fromkeys(cleaned))

    @field_validator("departements")
    @classmethod
    def _known_departements(cls, values: list[str]) -> list[str]:
        known = departements()
        cleaned = [value.strip().upper() for value in values]
        unknown = [v for v in cleaned if v not in known]
        if unknown:
            raise ValueError(f"Unknown département codes: {', '.join(unknown)}")
        return list(dict.fromkeys(cleaned))

    @field_validator("keywords")
    @classmethod
    def _short_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        too_long = [v for v in cleaned if len(v) > 60]
        if too_long:
            raise ValueError("Each keyword must be at most 60 characters.")
        return cleaned


class SegmentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)
    criteria: SegmentCriteria
    target_titles: list[str] = Field(
        min_length=1, max_length=6, description="Job titles of the decision makers to contact."
    )
    main_pain: str = Field(min_length=1, max_length=400)
    hook_angle: str = Field(min_length=1, max_length=400)
    fit_score: int = Field(ge=0, le=100)
    fit_rationale: str = Field(min_length=1, max_length=600)


class SegmentStrategy(BaseModel):
    """Output of Agent 2."""

    model_config = ConfigDict(extra="forbid")

    segments: list[SegmentProposal] = Field(min_length=3, max_length=6)


class SegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    offer_profile_id: uuid.UUID
    position: int
    name: str
    description: str
    criteria: SegmentCriteria
    target_titles: list[str]
    main_pain: str
    hook_angle: str
    fit_score: int
    fit_rationale: str
    selected: bool
    created_at: datetime


class SegmentSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected: bool
