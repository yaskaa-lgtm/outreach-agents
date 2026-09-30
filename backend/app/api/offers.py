"""Screen 1 (onboarding): analyse, edit and validate the offer profile."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_services
from app.auth.dependencies import CurrentUser
from app.core.errors import NotFoundError
from app.schemas.offer import AnalyzeOfferRequest, OfferProfileRead, OfferProfileUpdate
from app.schemas.segment import SegmentRead
from app.services import offers
from app.services.offers import AgentServices

router = APIRouter(prefix="/offer-profiles", tags=["offer profiles"])

Db = Annotated[AsyncSession, Depends(get_db)]
Services = Annotated[AgentServices, Depends(get_services)]


@router.get("/current")
async def current_profile(user: CurrentUser, db: Db) -> OfferProfileRead:
    profile = await offers.latest_profile(db, user.workspace_id)
    if profile is None:
        raise NotFoundError("No offer profile yet.")
    return OfferProfileRead.model_validate(profile)


@router.post("/analyze", status_code=status.HTTP_201_CREATED)
async def analyze(
    payload: AnalyzeOfferRequest, user: CurrentUser, db: Db, services: Services
) -> OfferProfileRead:
    """Runs Agent 1 (offer analyst). Can take up to a few minutes with a real LLM."""
    profile = await offers.analyze(db, services, user, payload)
    return OfferProfileRead.model_validate(profile)


@router.put("/{profile_id}")
async def update(
    profile_id: uuid.UUID, payload: OfferProfileUpdate, user: CurrentUser, db: Db
) -> OfferProfileRead:
    profile = await offers.update_profile(db, user, profile_id, payload.data)
    return OfferProfileRead.model_validate(profile)


@router.post("/{profile_id}/validate")
async def validate(profile_id: uuid.UUID, user: CurrentUser, db: Db) -> OfferProfileRead:
    profile = await offers.validate_profile(db, user, profile_id)
    return OfferProfileRead.model_validate(profile)


@router.get("/{profile_id}/segments")
async def list_segments(profile_id: uuid.UUID, user: CurrentUser, db: Db) -> list[SegmentRead]:
    segments = await offers.list_segments(db, user.workspace_id, profile_id)
    return [SegmentRead.model_validate(segment) for segment in segments]


@router.post("/{profile_id}/segments", status_code=status.HTTP_201_CREATED)
async def generate_segments(
    profile_id: uuid.UUID, user: CurrentUser, db: Db, services: Services
) -> list[SegmentRead]:
    """Runs Agent 2 (ICP strategist) on a validated profile; replaces previous segments."""
    segments = await offers.generate_segments(db, services, user, profile_id)
    return [SegmentRead.model_validate(segment) for segment in segments]
