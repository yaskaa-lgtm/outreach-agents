"""Offer profile: what the client sells, to whom, with a source for every claim (Agent 1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

# `source_url` value for claims taken from the description typed by the user.
USER_DESCRIPTION_SOURCE = "user-input:description"


class SourcedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=500, description="One factual statement.")
    source_url: str = Field(
        min_length=1,
        max_length=2048,
        description=(
            "URL of a page you fetched that supports the claim, or "
            f"'{USER_DESCRIPTION_SOURCE}' if it comes from the user's description."
        ),
    )
    excerpt: str = Field(
        min_length=1,
        max_length=400,
        description="Exact sentence or phrase copied from that source, supporting the claim.",
    )


class OfferProfileData(BaseModel):
    """Output of Agent 1. Lists may be empty: never fill gaps with guesses."""

    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(max_length=200)
    summary: str = Field(
        min_length=1,
        max_length=1000,
        description="Two or three sentences: what the company sells and to whom.",
    )
    offerings: list[SourcedClaim] = Field(max_length=10, description="Products or services.")
    target_customers: list[SourcedClaim] = Field(max_length=10)
    value_proposition: SourcedClaim | None
    differentiators: list[SourcedClaim] = Field(max_length=10)
    pricing: list[SourcedClaim] = Field(max_length=5, description="Only if prices are public.")
    geography: list[SourcedClaim] = Field(max_length=5, description="Where they operate.")
    proof_points: list[SourcedClaim] = Field(
        max_length=10, description="Named customers, figures, certifications, awards."
    )
    competitors_mentioned: list[SourcedClaim] = Field(max_length=10)
    missing_information: list[str] = Field(
        max_length=10, description="Important facts that the sources do not contain."
    )

    def claim_lists(self) -> dict[str, list[SourcedClaim]]:
        return {
            "offerings": self.offerings,
            "target_customers": self.target_customers,
            "differentiators": self.differentiators,
            "pricing": self.pricing,
            "geography": self.geography,
            "proof_points": self.proof_points,
            "competitors_mentioned": self.competitors_mentioned,
        }


class AnalyzeOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _at_least_one_input(self) -> AnalyzeOfferRequest:
        if self.website_url is None and not (self.description and self.description.strip()):
            raise ValueError("Provide a website URL, a description, or both.")
        return self


class OfferProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OfferProfileData


class OfferProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["draft", "validated"]
    source_url: str | None
    source_description: str | None
    data: OfferProfileData
    warnings: list[str]
    pages_fetched: list[str]
    created_at: datetime
    updated_at: datetime
    validated_at: datetime | None
