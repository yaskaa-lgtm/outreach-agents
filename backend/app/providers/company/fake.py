"""Fictional companies for tests and demo mode (Faker, `example.com` domains only).

The SIREN is part of the domain (`<slug>-<siren>.example.com`) so that the demo website
can show a legal notice page carrying that SIREN, exactly like a real site would.
"""

from __future__ import annotations

import hashlib
import random
import re
import unicodedata

from faker import Faker

from app.providers.company.base import CompanyCandidate, Officer
from app.schemas.segment import SegmentCriteria

DEMO_DOMAIN_SUFFIX = ".example.com"
DEMO_DOMAIN_PATTERN = re.compile(r"^[a-z0-9-]+-(\d{9})\.example\.com$")


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40] or "entreprise"


def _seed(criteria: SegmentCriteria) -> int:
    digest = hashlib.sha256(criteria.model_dump_json().encode()).hexdigest()
    return int(digest[:12], 16)


class FakeCompanyProvider:
    name = "fake"

    async def search(self, criteria: SegmentCriteria, limit: int) -> list[CompanyCandidate]:
        seed = _seed(criteria)
        faker = Faker("fr_FR")
        faker.seed_instance(seed)
        rng = random.Random(seed)  # noqa: S311 (fake data, not security)
        companies = []
        for _ in range(limit):
            name = faker.company()
            siren = faker.siren().replace(" ", "")
            postal_code = faker.postcode()
            departement = (
                rng.choice(criteria.departements) if criteria.departements else postal_code[:2]
            )
            companies.append(
                CompanyCandidate(
                    name=name,
                    source="fake",
                    siren=siren,
                    naf_code=rng.choice(criteria.naf_codes),
                    headcount_range=rng.choice(criteria.headcount_ranges),
                    postal_code=postal_code,
                    city=faker.city(),
                    departement=departement,
                    website_domain=f"{_slug(name)}-{siren}{DEMO_DOMAIN_SUFFIX}",
                    officers=[
                        Officer(
                            first_names=faker.first_name(),
                            last_name=faker.last_name(),
                            role="Gérant",
                        )
                    ],
                )
            )
        return companies
