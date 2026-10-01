"""Common types for contact providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

VerificationStatus = (
    str  # unverified | valid | accept_all | unknown | invalid | webmail | disposable
)


@dataclass(frozen=True)
class ContactCandidate:
    first_name: str | None
    last_name: str | None
    title: str | None
    email: str | None
    source: str
    source_url: str | None = None
    # Verification already done by the provider (e.g. Hunter's own check), if any.
    verification_status: VerificationStatus | None = None


class ContactFinder(Protocol):
    name: str

    async def find(self, domain: str) -> list[ContactCandidate]: ...


class DomainFinder(Protocol):
    async def domain_for(self, company_name: str) -> str | None: ...


class EmailVerifier(Protocol):
    async def verify(self, email: str) -> VerificationStatus: ...


class NoEmailVerifier:
    """Used when no verification service is configured: nothing can become sendable."""

    async def verify(self, email: str) -> VerificationStatus:
        return "unverified"
