"""Campaign use cases (screen 3): launch discovery on selected segments, import a CSV,
follow the prospects."""

from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthenticatedUser
from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.discovery.pipeline import add_prospect, upsert_company
from app.models import (
    Campaign,
    CampaignSegment,
    Company,
    Contact,
    Job,
    Prospect,
    ProspectTransition,
    Segment,
)
from app.providers.company.csv_import import CsvImportError, parse_companies_csv
from app.schemas.campaign import (
    CampaignCreate,
    CampaignRead,
    CompanySummary,
    ContactSummary,
    CsvImportResult,
    JobProgress,
    ProspectDetail,
    ProspectRow,
    TransitionRead,
)
from app.services import audit
from app.services.offers import latest_profile
from app.worker.queue import enqueue


class InvalidCsvError(AppError):
    status_code = 422
    code = "invalid_csv"


async def create_campaign(
    db: AsyncSession, settings: Settings, user: AuthenticatedUser, payload: CampaignCreate
) -> Campaign:
    profile = await latest_profile(db, user.workspace_id)
    if profile is None or profile.status != "validated":
        raise ConflictError("Validate the offer profile before launching a campaign.")
    segments = list(
        await db.scalars(
            select(Segment).where(
                Segment.id.in_(payload.segment_ids),
                Segment.workspace_id == user.workspace_id,
                Segment.offer_profile_id == profile.id,
            )
        )
    )
    if len(segments) != len(set(payload.segment_ids)):
        raise NotFoundError("Some segments do not belong to the current offer profile.")

    per_segment = min(
        payload.companies_per_segment or settings.companies_per_segment,
        settings.companies_per_segment_max,
    )
    campaign = Campaign(
        workspace_id=user.workspace_id,
        offer_profile_id=profile.id,
        name=payload.name,
        companies_per_segment=per_segment,
    )
    db.add(campaign)
    await db.flush()
    for segment in segments:
        db.add(
            CampaignSegment(
                workspace_id=user.workspace_id, campaign_id=campaign.id, segment_id=segment.id
            )
        )
        await enqueue(
            db,
            workspace_id=user.workspace_id,
            kind="discover_companies",
            payload={"campaign_id": str(campaign.id), "segment_id": str(segment.id)},
            idempotency_key=f"discover_companies:{campaign.id}:{segment.id}",
            correlation_id=campaign.id,
        )
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="campaign.created",
        entity_type="campaign",
        entity_id=campaign.id,
        details={"segments": len(segments), "companies_per_segment": per_segment},
    )
    await db.commit()
    return campaign


async def _get_campaign(
    db: AsyncSession, workspace_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = await db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    )
    if campaign is None:
        raise NotFoundError("Campaign not found.")
    return campaign


async def campaign_read(db: AsyncSession, campaign: Campaign) -> CampaignRead:
    segment_ids = list(
        await db.scalars(
            select(CampaignSegment.segment_id).where(CampaignSegment.campaign_id == campaign.id)
        )
    )
    states = await db.execute(
        select(Prospect.state, func.count())
        .where(Prospect.campaign_id == campaign.id)
        .group_by(Prospect.state)
    )
    jobs = await db.execute(
        select(Job.status, func.count())
        .where(Job.correlation_id == campaign.id)
        .group_by(Job.status)
    )
    job_counts = Counter({status: count for status, count in jobs.all()})
    return CampaignRead(
        id=campaign.id,
        name=campaign.name,
        created_at=campaign.created_at,
        companies_per_segment=campaign.companies_per_segment,
        segment_ids=segment_ids,
        counts={state: count for state, count in states.all()},
        jobs=JobProgress(
            pending=job_counts["queued"] + job_counts["running"], failed=job_counts["dead"]
        ),
    )


async def list_campaigns(db: AsyncSession, workspace_id: uuid.UUID) -> list[CampaignRead]:
    campaigns = await db.scalars(
        select(Campaign)
        .where(Campaign.workspace_id == workspace_id)
        .order_by(Campaign.created_at.desc())
    )
    return [await campaign_read(db, campaign) for campaign in campaigns]


async def get_campaign(
    db: AsyncSession, workspace_id: uuid.UUID, campaign_id: uuid.UUID
) -> CampaignRead:
    return await campaign_read(db, await _get_campaign(db, workspace_id, campaign_id))


def _row(prospect: Prospect, company: Company, contact: Contact | None) -> ProspectRow:
    return ProspectRow(
        id=prospect.id,
        state=prospect.state,
        state_reason=prospect.state_reason,
        segment_id=prospect.segment_id,
        company=CompanySummary.model_validate(company),
        contact=ContactSummary.model_validate(contact) if contact else None,
    )


async def list_prospects(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    campaign_id: uuid.UUID,
    state: str | None = None,
    segment_id: uuid.UUID | None = None,
) -> list[ProspectRow]:
    await _get_campaign(db, workspace_id, campaign_id)
    query = (
        select(Prospect, Company, Contact)
        .join(Company, Company.id == Prospect.company_id)
        .outerjoin(Contact, Contact.id == Prospect.contact_id)
        .where(Prospect.campaign_id == campaign_id, Prospect.workspace_id == workspace_id)
        .order_by(Company.name)
    )
    if state:
        query = query.where(Prospect.state == state)
    if segment_id:
        query = query.where(Prospect.segment_id == segment_id)
    rows = await db.execute(query)
    return [_row(prospect, company, contact) for prospect, company, contact in rows.all()]


async def get_prospect(
    db: AsyncSession, workspace_id: uuid.UUID, prospect_id: uuid.UUID
) -> ProspectDetail:
    row = (
        await db.execute(
            select(Prospect, Company, Contact)
            .join(Company, Company.id == Prospect.company_id)
            .outerjoin(Contact, Contact.id == Prospect.contact_id)
            .where(Prospect.id == prospect_id, Prospect.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Prospect not found.")
    prospect, company, contact = row
    transitions = await db.scalars(
        select(ProspectTransition)
        .where(ProspectTransition.prospect_id == prospect.id)
        .order_by(ProspectTransition.created_at)
    )
    base = _row(prospect, company, contact)
    return ProspectDetail(
        **base.model_dump(),
        campaign_id=prospect.campaign_id,
        transitions=[TransitionRead.model_validate(t) for t in transitions],
    )


async def import_csv(
    db: AsyncSession, user: AuthenticatedUser, campaign_id: uuid.UUID, text: str
) -> CsvImportResult:
    campaign = await _get_campaign(db, user.workspace_id, campaign_id)
    try:
        parsed = parse_companies_csv(text)
    except CsvImportError as exc:
        raise InvalidCsvError(str(exc)) from exc
    imported = duplicates = 0
    for candidate in parsed.candidates:
        company = await upsert_company(db, user.workspace_id, candidate)
        if await add_prospect(db, campaign, company, segment_id=None) is None:
            duplicates += 1
        else:
            imported += 1
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="campaign.csv_imported",
        entity_type="campaign",
        entity_id=campaign.id,
        details={"imported": imported, "duplicates": duplicates, "errors": len(parsed.errors)},
    )
    await db.commit()
    return CsvImportResult(imported=imported, already_in_campaign=duplicates, errors=parsed.errors)
