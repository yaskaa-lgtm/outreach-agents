"""Common types for company providers: one interface, several sources (provider pattern)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.segment import SegmentCriteria


@dataclass(frozen=True)
class Officer:
    """A company officer from the official registry (no birth date, no nationality)."""

    first_names: str
    last_name: str
    role: str | None


@dataclass(frozen=True)
class ProvidedContact:
    """A contact supplied with the company (CSV import only)."""

    first_name: str | None
    last_name: str | None
    title: str | None
    email: str | None


@dataclass(frozen=True)
class CompanyCandidate:
    name: str
    source: str
    siren: str | None = None
    naf_code: str | None = None
    headcount_range: str | None = None
    postal_code: str | None = None
    city: str | None = None
    departement: str | None = None
    is_sole_trader: bool = False
    # Website given by the source, still to be confirmed by the SIREN check.
    website_domain: str | None = None
    officers: list[Officer] = field(default_factory=list)
    contacts: list[ProvidedContact] = field(default_factory=list)


class CompanyProvider(Protocol):
    name: str

    async def search(self, criteria: SegmentCriteria, limit: int) -> list[CompanyCandidate]: ...


def is_valid_siren(siren: str) -> bool:
    """9 digits with a valid Luhn checksum (INSEE rule)."""
    if len(siren) != 9 or not siren.isdigit():
        return False
    total = 0
    for index, char in enumerate(reversed(siren)):
        digit = int(char) * (2 if index % 2 else 1)
        total += digit - 9 if digit > 9 else digit
    return total % 10 == 0
