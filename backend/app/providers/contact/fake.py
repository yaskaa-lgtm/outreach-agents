"""Fictional contacts and verification for tests and demo mode (Faker, example.com only).

Deterministic per domain, with a realistic mix: most addresses are valid, some cannot be
verified (accept_all / unknown) and a few are personal webmail addresses that must be
excluded — so the demo shows every rule at work.
"""

from __future__ import annotations

import hashlib
import unicodedata

from faker import Faker

from app.providers.contact.base import ContactCandidate, VerificationStatus


def _ascii(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .replace(" ", "-")
    )


def _bucket(text: str, size: int) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % size


class FakeContactFinder:
    name = "fake"

    async def find(self, domain: str) -> list[ContactCandidate]:
        faker = Faker("fr_FR")
        faker.seed_instance(_bucket(domain, 10**9))
        first, last = faker.first_name(), faker.last_name()
        kind = _bucket(domain, 10)
        if kind == 0:
            # A personal address: must be excluded by the webmail rule. Reserved domain, so
            # the generated address can never belong to a real person.
            email = f"{_ascii(first)}.{_ascii(last)}@webmail.example"
        elif kind == 1:
            email = f"contact@{domain}"
        else:
            email = f"{_ascii(first)}.{_ascii(last)}@{domain}"
        return [
            ContactCandidate(
                first_name=None if email.startswith("contact@") else first,
                last_name=None if email.startswith("contact@") else last,
                title=None if email.startswith("contact@") else "Gérant",
                email=email,
                source="fake",
                source_url=f"https://{domain}/",
            )
        ]


class FakeEmailVerifier:
    async def verify(self, email: str) -> VerificationStatus:
        bucket = _bucket(email, 10)
        if bucket == 0:
            return "accept_all"
        if bucket == 1:
            return "unknown"
        return "valid"
