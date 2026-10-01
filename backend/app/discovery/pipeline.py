"""Discovery jobs run by the worker.

1. `discover_companies` (Agent 3): companies matching one segment of a campaign, de-duplicated
   by SIREN then by domain; each new company becomes a prospect in state `discovered`.
2. `process_prospect` (Agent 4): confirm the company's domain (SIREN check), pick the best
   decision maker, verify the address -> `contact_found` / `email_verified` / `excluded`.

Both jobs are idempotent: running them twice changes nothing the second time.
"""

from __future__ import annotations

import logging
import unicodedata
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.compliance.email_rules import (
    NEVER_SENDABLE_STATUSES,
    SENDABLE_STATUSES,
    email_domain,
    email_hash,
    is_generic,
    is_valid_syntax,
    is_webmail,
    normalize_email,
)
from app.core.config import Settings
from app.core.logging import mask_email
from app.demo.site import DemoWebFetcher
from app.discovery.domains import confirm_domain
from app.models import Campaign, Company, Contact, Prospect, ProspectTransition, Segment
from app.orchestrator.states import check_transition
from app.providers.company.base import CompanyCandidate, CompanyProvider
from app.providers.company.fake import FakeCompanyProvider
from app.providers.company.registry import RegistryCompanyProvider
from app.providers.contact.base import (
    ContactCandidate,
    ContactFinder,
    DomainFinder,
    EmailVerifier,
    NoEmailVerifier,
)
from app.providers.contact.fake import FakeContactFinder, FakeEmailVerifier
from app.providers.contact.hunter import HunterClient, HunterCreditsExhaustedError, HunterError
from app.providers.web.fetcher import SafeWebFetcher, WebFetcher
from app.schemas.segment import SegmentCriteria
from app.worker.queue import enqueue

logger = logging.getLogger(__name__)

ACTOR = "system:discovery"


@dataclass
class DiscoveryProviders:
    company: CompanyProvider
    contact_finder: ContactFinder | None
    domain_finder: DomainFinder | None
    verifier: EmailVerifier
    fetcher_factory: Callable[[], AbstractAsyncContextManager[WebFetcher]]
    _closers: list[Any] = field(default_factory=list)

    async def aclose(self) -> None:
        for resource in self._closers:
            await resource.aclose()


def build_providers(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], workspace_id: uuid.UUID
) -> DiscoveryProviders:
    if settings.demo_mode:
        return DiscoveryProviders(
            company=FakeCompanyProvider(),
            contact_finder=FakeContactFinder(),
            domain_finder=None,
            verifier=FakeEmailVerifier(),
            fetcher_factory=DemoWebFetcher,
        )
    registry = RegistryCompanyProvider(settings)
    closers: list[Any] = [registry]
    hunter: HunterClient | None = None
    if settings.hunter_api_key is not None:
        hunter = HunterClient(
            settings.hunter_api_key.get_secret_value(),
            sessionmaker,
            workspace_id,
            settings.hunter_monthly_credit_limit,
        )
        closers.append(hunter)
    return DiscoveryProviders(
        company=registry,
        contact_finder=hunter,
        domain_finder=hunter,
        verifier=hunter or NoEmailVerifier(),
        fetcher_factory=lambda: SafeWebFetcher(settings),
        _closers=closers,
    )


# --- state machine ------------------------------------------------------------------------
def move(db: AsyncSession, prospect: Prospect, to_state: str, reason: str | None = None) -> None:
    check_transition(prospect.state, to_state, reason)
    db.add(
        ProspectTransition(
            workspace_id=prospect.workspace_id,
            prospect_id=prospect.id,
            from_state=prospect.state,
            to_state=to_state,
            reason=reason,
            actor=ACTOR,
        )
    )
    prospect.state = to_state
    prospect.state_reason = reason


# --- companies ------------------------------------------------------------------------------
async def upsert_company(
    db: AsyncSession, workspace_id: uuid.UUID, candidate: CompanyCandidate
) -> Company:
    company: Company | None = None
    if candidate.siren:
        company = await db.scalar(
            select(Company).where(
                Company.workspace_id == workspace_id, Company.siren == candidate.siren
            )
        )
    if company is None and candidate.website_domain:
        company = await db.scalar(
            select(Company).where(
                Company.workspace_id == workspace_id,
                Company.website_domain == candidate.website_domain,
            )
        )
    if company is None:
        company = Company(
            workspace_id=workspace_id,
            siren=candidate.siren,
            name=candidate.name[:300],
            source_provider=candidate.source,
            domain_status="unknown",
        )
        db.add(company)
    for attribute in ("naf_code", "headcount_range", "postal_code", "city", "departement"):
        if getattr(company, attribute) is None and getattr(candidate, attribute):
            setattr(company, attribute, getattr(candidate, attribute))
    company.is_sole_trader = company.is_sole_trader or candidate.is_sole_trader
    if company.website_domain is None and candidate.website_domain:
        company.website_domain = candidate.website_domain
        company.domain_source = candidate.source
    if not company.officers and candidate.officers:
        company.officers = [
            {"first_names": o.first_names, "last_name": o.last_name, "role": o.role}
            for o in candidate.officers
        ]
    await db.flush()
    for provided in candidate.contacts:
        await _add_provided_contact(
            db, company, provided.first_name, provided.last_name, provided.title, provided.email
        )
    return company


async def _add_provided_contact(
    db: AsyncSession,
    company: Company,
    first_name: str | None,
    last_name: str | None,
    title: str | None,
    email: str | None,
) -> None:
    hashed = email_hash(email) if email else None
    if hashed and await db.scalar(
        select(Contact.id).where(
            Contact.workspace_id == company.workspace_id, Contact.email_hash == hashed
        )
    ):
        return
    db.add(
        Contact(
            workspace_id=company.workspace_id,
            company_id=company.id,
            first_name=first_name,
            last_name=last_name,
            title=title,
            email=normalize_email(email) if email else None,
            email_hash=hashed,
            is_generic=is_generic(email) if email else False,
            source_provider="csv",
        )
    )
    await db.flush()


async def add_prospect(
    db: AsyncSession, campaign: Campaign, company: Company, segment_id: uuid.UUID | None
) -> Prospect | None:
    """Create the prospect and queue its processing; None if the company is already in."""
    existing = await db.scalar(
        select(Prospect.id).where(
            Prospect.campaign_id == campaign.id, Prospect.company_id == company.id
        )
    )
    if existing is not None:
        return None
    prospect = Prospect(
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
        segment_id=segment_id,
        company_id=company.id,
        state="discovered",
    )
    db.add(prospect)
    await db.flush()
    db.add(
        ProspectTransition(
            workspace_id=campaign.workspace_id,
            prospect_id=prospect.id,
            from_state=None,
            to_state="discovered",
            reason=f"source: {company.source_provider}",
            actor=ACTOR,
        )
    )
    await enqueue(
        db,
        workspace_id=campaign.workspace_id,
        kind="process_prospect",
        payload={"prospect_id": str(prospect.id)},
        idempotency_key=f"process_prospect:{prospect.id}",
        correlation_id=campaign.id,
    )
    return prospect


async def discover_companies(
    sessionmaker: async_sessionmaker[AsyncSession],
    providers: DiscoveryProviders,
    payload: dict[str, Any],
) -> int:
    async with sessionmaker() as db:
        campaign = await db.get(Campaign, uuid.UUID(payload["campaign_id"]))
        segment = await db.get(Segment, uuid.UUID(payload["segment_id"]))
        if campaign is None or segment is None:
            return 0
        criteria = SegmentCriteria.model_validate(segment.criteria)
        workspace_id, limit, campaign_id = (
            campaign.workspace_id,
            campaign.companies_per_segment,
            campaign.id,
        )

    candidates = await providers.company.search(criteria, limit)

    created = 0
    async with sessionmaker() as db:
        campaign = await db.get(Campaign, campaign_id)
        if campaign is None:  # deleted in the meantime
            return 0
        for candidate in candidates:
            company = await upsert_company(db, workspace_id, candidate)
            if await add_prospect(db, campaign, company, segment.id) is not None:
                created += 1
        await db.commit()
    logger.info("Discovered %d new companies for one segment", created)
    return created


# --- contacts ---------------------------------------------------------------------------------
def _words(text: str | None) -> set[str]:
    ascii_text = (
        unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    )
    return {word for word in ascii_text.replace("-", " ").split() if len(word) > 2}


def rank_contact(
    candidate: ContactCandidate, target_titles: list[str]
) -> tuple[int, int, int, int]:
    """Higher is better: has an address, title match, named person, not generic.

    A reachable contact always beats an unreachable one (a registry officer without an
    address cannot be emailed); among reachable ones, the targeted titles come first.
    """
    targets = set().union(*(_words(title) for title in target_titles)) if target_titles else set()
    title_match = len(_words(candidate.title) & targets)
    named = int(bool(candidate.first_name or candidate.last_name))
    generic = int(bool(candidate.email and is_generic(candidate.email)))
    return (int(bool(candidate.email)), title_match, named, -generic)


async def _candidates(
    db: AsyncSession, company: Company, providers: DiscoveryProviders
) -> tuple[list[ContactCandidate], str | None]:
    note: str | None = None
    candidates: list[ContactCandidate] = []
    if company.domain_status == "confirmed" and company.website_domain and providers.contact_finder:
        try:
            candidates += await providers.contact_finder.find(company.website_domain)
        except HunterCreditsExhaustedError:
            note = "Hunter monthly credit limit reached"
        except HunterError as exc:
            note = str(exc)
    existing = await db.scalars(select(Contact).where(Contact.company_id == company.id))
    for contact in existing:
        candidates.append(
            ContactCandidate(
                first_name=contact.first_name,
                last_name=contact.last_name,
                title=contact.title,
                email=contact.email,
                source=contact.source_provider,
            )
        )
    for officer in company.officers or []:
        candidates.append(
            ContactCandidate(
                first_name=officer.get("first_names"),
                last_name=officer.get("last_name"),
                title=officer.get("role"),
                email=None,
                source="registry",
                source_url="https://recherche-entreprises.api.gouv.fr",
            )
        )
    return candidates, note


async def _store_contact(
    db: AsyncSession, company: Company, candidate: ContactCandidate
) -> Contact:
    hashed = email_hash(candidate.email) if candidate.email else None
    contact: Contact | None = None
    if hashed:
        contact = await db.scalar(
            select(Contact).where(
                Contact.workspace_id == company.workspace_id, Contact.email_hash == hashed
            )
        )
    if contact is None:
        contact = await db.scalar(
            select(Contact).where(
                Contact.company_id == company.id,
                Contact.first_name == candidate.first_name,
                Contact.last_name == candidate.last_name,
                Contact.email.is_(None)
                if candidate.email is None
                else Contact.email == normalize_email(candidate.email),
            )
        )
    if contact is None:
        contact = Contact(
            workspace_id=company.workspace_id,
            company_id=company.id,
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            title=candidate.title,
            email=normalize_email(candidate.email) if candidate.email else None,
            email_hash=hashed,
            is_generic=is_generic(candidate.email) if candidate.email else False,
            source_provider=candidate.source,
            source_url=candidate.source_url,
        )
        db.add(contact)
        await db.flush()
    return contact


async def _verification_status(
    contact: Contact, company: Company, candidate: ContactCandidate, verifier: EmailVerifier
) -> tuple[str, str | None]:
    email = contact.email or ""
    if not is_valid_syntax(email):
        return "invalid", "malformed address"
    if is_webmail(email):
        return "webmail", "personal webmail address (B2B only)"
    if company.domain_status != "confirmed" or email_domain(email) != company.website_domain:
        return "unverified", "address not on the company's confirmed domain"
    if candidate.verification_status in SENDABLE_STATUSES | NEVER_SENDABLE_STATUSES:
        return candidate.verification_status or "unknown", None
    try:
        return await verifier.verify(email), None
    except HunterCreditsExhaustedError:
        return "unverified", "Hunter monthly credit limit reached"
    except HunterError as exc:
        return "unverified", str(exc)


async def process_prospect(
    sessionmaker: async_sessionmaker[AsyncSession],
    providers: DiscoveryProviders,
    settings: Settings,
    payload: dict[str, Any],
) -> str:
    async with sessionmaker() as db:
        prospect = await db.get(Prospect, uuid.UUID(payload["prospect_id"]))
        if prospect is None or prospect.state != "discovered":
            return "skipped"
        company = await db.get(Company, prospect.company_id)
        segment = await db.get(Segment, prospect.segment_id) if prospect.segment_id else None
        if company is None:
            return "skipped"
        target_titles = list(segment.target_titles) if segment else []

        # 1. Domain: candidate from the source (or Hunter), confirmed by the SIREN.
        if company.domain_status != "confirmed":
            if company.website_domain is None and providers.domain_finder is not None:
                try:
                    found = await providers.domain_finder.domain_for(company.name)
                except (HunterCreditsExhaustedError, HunterError):
                    found = None
                if found:
                    company.website_domain, company.domain_source = found, "hunter"
            if company.website_domain and company.siren:
                async with providers.fetcher_factory() as fetcher:
                    check = await confirm_domain(
                        fetcher,
                        company.siren,
                        company.website_domain,
                        settings.domain_check_max_pages,
                    )
                company.domain_status, company.domain_evidence_url = (
                    check.status,
                    check.evidence_url,
                )
            elif not company.website_domain:
                company.domain_status = "not_found"
            else:
                company.domain_status = "unconfirmed"  # no SIREN to check against (CSV row)

        # 2. Decision maker.
        candidates, note = await _candidates(db, company, providers)
        if not candidates:
            move(db, prospect, "excluded", note or "no decision maker found")
            await db.commit()
            return prospect.state
        best = max(candidates, key=lambda c: rank_contact(c, target_titles))
        contact = await _store_contact(db, company, best)
        prospect.contact_id = contact.id
        move(db, prospect, "contact_found")

        # 3. Address verification: only `valid` becomes sendable.
        if not contact.email:
            prospect.state_reason = note or (
                "no professional address found"
                if providers.contact_finder
                else "no professional address found (no contact provider configured)"
            )
        else:
            status, reason = await _verification_status(contact, company, best, providers.verifier)
            contact.verification_status = status
            contact.verified_at = datetime.now(UTC) if status != "unverified" else None
            if status in SENDABLE_STATUSES:
                move(db, prospect, "email_verified")
            elif status in NEVER_SENDABLE_STATUSES:
                move(db, prospect, "excluded", reason or f"address status: {status}")
            else:
                prospect.state_reason = reason or f"address status '{status}' is not sendable"
            logger.info("Checked %s: %s", mask_email(contact.email), status)
        await db.commit()
        return prospect.state
