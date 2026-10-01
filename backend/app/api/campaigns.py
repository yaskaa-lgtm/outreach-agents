"""Screen 3 (campaign): launch discovery, import a CSV, follow prospects and their states."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.campaign import (
    CampaignCreate,
    CampaignRead,
    CsvImportRequest,
    CsvImportResult,
    ProspectDetail,
    ProspectRow,
)
from app.services import campaigns

router = APIRouter(tags=["campaigns"])

Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate, request: Request, user: CurrentUser, db: Db
) -> CampaignRead:
    """Creates the campaign and queues company discovery for each segment (worker)."""
    campaign = await campaigns.create_campaign(db, request.app.state.settings, user, payload)
    return await campaigns.campaign_read(db, campaign)


@router.get("/campaigns")
async def list_campaigns(user: CurrentUser, db: Db) -> list[CampaignRead]:
    return await campaigns.list_campaigns(db, user.workspace_id)


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: Db) -> CampaignRead:
    return await campaigns.get_campaign(db, user.workspace_id, campaign_id)


@router.get("/campaigns/{campaign_id}/prospects")
async def list_prospects(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    state: Annotated[str | None, Query(max_length=30)] = None,
    segment_id: uuid.UUID | None = None,
) -> list[ProspectRow]:
    return await campaigns.list_prospects(db, user.workspace_id, campaign_id, state, segment_id)


@router.post("/campaigns/{campaign_id}/import", status_code=status.HTTP_201_CREATED)
async def import_csv(
    campaign_id: uuid.UUID, payload: CsvImportRequest, user: CurrentUser, db: Db
) -> CsvImportResult:
    return await campaigns.import_csv(db, user, campaign_id, payload.csv)


@router.get("/prospects/{prospect_id}")
async def get_prospect(prospect_id: uuid.UUID, user: CurrentUser, db: Db) -> ProspectDetail:
    return await campaigns.get_prospect(db, user.workspace_id, prospect_id)
