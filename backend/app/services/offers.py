"""Onboarding use cases: analyse the offer (Agent 1), edit and validate it, propose
segments (Agent 2), select segments.

Phase 1 runs the agents inside the HTTP request. From Phase 2 on, long agent work moves
to the PostgreSQL job queue and the worker (see docs/PLAN.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.icp_strategist import propose_segments
from app.agents.offer_analyst import analyze_offer
from app.auth.service import AuthenticatedUser
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.demo.site import DEMO_WEBSITE_URL, DemoWebFetcher
from app.models import OfferProfile, Segment
from app.providers.llm.base import LLMClient
from app.providers.llm.factory import build_llm_client
from app.providers.llm.metering import CostCalculator, MeteredLLMClient
from app.providers.web.fetcher import SafeWebFetcher, WebFetcher
from app.providers.web.url_safety import validate_url
from app.schemas.offer import AnalyzeOfferRequest, OfferProfileData
from app.services import audit

FetcherFactory = Callable[[], AbstractAsyncContextManager[WebFetcher]]


@dataclass
class AgentServices:
    """Everything the agents need, built once at start-up (and replaced in tests)."""

    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    llm_factory: Callable[[], LLMClient]
    fetcher_factory: FetcherFactory
    costs: CostCalculator

    @classmethod
    def from_settings(
        cls, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> AgentServices:
        def fetcher_factory() -> AbstractAsyncContextManager[WebFetcher]:
            if settings.demo_mode:
                return DemoWebFetcher()
            return SafeWebFetcher(settings)

        return cls(
            settings=settings,
            sessionmaker=sessionmaker,
            llm_factory=lambda: build_llm_client(settings),
            fetcher_factory=fetcher_factory,
            costs=CostCalculator.from_settings(settings)
            if not settings.missing_llm_settings()
            else CostCalculator.free(),
        )

    def metered_llm(self, workspace_id: uuid.UUID) -> MeteredLLMClient:
        return MeteredLLMClient(self.llm_factory(), self.sessionmaker, workspace_id, self.costs)


async def latest_profile(db: AsyncSession, workspace_id: uuid.UUID) -> OfferProfile | None:
    return await db.scalar(
        select(OfferProfile)
        .where(OfferProfile.workspace_id == workspace_id)
        .order_by(OfferProfile.created_at.desc())
        .limit(1)
    )


async def get_profile(
    db: AsyncSession, workspace_id: uuid.UUID, profile_id: uuid.UUID
) -> OfferProfile:
    profile = await db.scalar(
        select(OfferProfile).where(
            OfferProfile.id == profile_id, OfferProfile.workspace_id == workspace_id
        )
    )
    if profile is None:
        raise NotFoundError("Offer profile not found.")
    return profile


async def analyze(
    db: AsyncSession, services: AgentServices, user: AuthenticatedUser, request: AnalyzeOfferRequest
) -> OfferProfile:
    settings = services.settings
    website = str(request.website_url) if request.website_url else None
    warnings: list[str] = []
    if settings.demo_mode and website and website != DEMO_WEBSITE_URL:
        warnings.append(
            f"Demo mode: the fictional website {DEMO_WEBSITE_URL} was analysed "
            f"instead of {website}."
        )
        website = DEMO_WEBSITE_URL
    if website:
        validate_url(website)  # fail fast with a clear message before any LLM cost

    llm = services.metered_llm(user.workspace_id)
    async with services.fetcher_factory() as fetcher:
        result = await analyze_offer(
            llm=llm,
            fetcher=fetcher,
            website_url=website,
            description=request.description,
            max_pages=settings.offer_analysis_max_pages,
            max_tokens=settings.llm_max_output_tokens,
        )

    profile = OfferProfile(
        workspace_id=user.workspace_id,
        source_url=website,
        source_description=request.description,
        data=result.data.model_dump(mode="json"),
        status="draft",
        warnings=warnings + result.warnings,
        pages_fetched=result.pages_fetched,
    )
    db.add(profile)
    await db.flush()
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="offer_profile.analyzed",
        entity_type="offer_profile",
        entity_id=profile.id,
        details={
            "pages_fetched": len(result.pages_fetched),
            "claims_removed": len(result.warnings),
        },
    )
    await db.commit()
    return profile


async def update_profile(
    db: AsyncSession, user: AuthenticatedUser, profile_id: uuid.UUID, data: OfferProfileData
) -> OfferProfile:
    profile = await get_profile(db, user.workspace_id, profile_id)
    profile.data = data.model_dump(mode="json")
    # Any edit needs a new human validation before segments can be generated.
    profile.status = "draft"
    profile.validated_at = None
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="offer_profile.edited",
        entity_type="offer_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return profile


async def validate_profile(
    db: AsyncSession, user: AuthenticatedUser, profile_id: uuid.UUID
) -> OfferProfile:
    profile = await get_profile(db, user.workspace_id, profile_id)
    profile.status = "validated"
    profile.validated_at = datetime.now(UTC)
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="offer_profile.validated",
        entity_type="offer_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return profile


async def list_segments(
    db: AsyncSession, workspace_id: uuid.UUID, profile_id: uuid.UUID
) -> list[Segment]:
    await get_profile(db, workspace_id, profile_id)
    rows = await db.scalars(
        select(Segment)
        .where(Segment.offer_profile_id == profile_id, Segment.workspace_id == workspace_id)
        .order_by(Segment.position)
    )
    return list(rows)


async def generate_segments(
    db: AsyncSession, services: AgentServices, user: AuthenticatedUser, profile_id: uuid.UUID
) -> list[Segment]:
    profile = await get_profile(db, user.workspace_id, profile_id)
    if profile.status != "validated":
        raise ConflictError("Validate the offer profile before generating segments.")
    offer = OfferProfileData.model_validate(profile.data)

    strategy = await propose_segments(
        llm=services.metered_llm(user.workspace_id),
        offer=offer,
        max_tokens=services.settings.llm_max_output_tokens,
    )

    await db.execute(delete(Segment).where(Segment.offer_profile_id == profile.id))
    segments = [
        Segment(
            workspace_id=user.workspace_id,
            offer_profile_id=profile.id,
            position=index,
            name=proposal.name,
            description=proposal.description,
            criteria=proposal.criteria.model_dump(mode="json"),
            target_titles=proposal.target_titles,
            main_pain=proposal.main_pain,
            hook_angle=proposal.hook_angle,
            fit_score=proposal.fit_score,
            fit_rationale=proposal.fit_rationale,
            selected=False,
        )
        for index, proposal in enumerate(strategy.segments)
    ]
    db.add_all(segments)
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="segments.generated",
        entity_type="offer_profile",
        entity_id=profile.id,
        details={"count": len(segments)},
    )
    await db.commit()
    return segments


async def set_segment_selected(
    db: AsyncSession, user: AuthenticatedUser, segment_id: uuid.UUID, selected: bool
) -> Segment:
    segment = await db.scalar(
        select(Segment).where(Segment.id == segment_id, Segment.workspace_id == user.workspace_id)
    )
    if segment is None:
        raise NotFoundError("Segment not found.")
    segment.selected = selected
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="segment.selected" if selected else "segment.unselected",
        entity_type="segment",
        entity_id=segment.id,
    )
    await db.commit()
    return segment
