"""Screen 2 (segments): choose which segments to launch."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.segment import SegmentRead, SegmentSelection
from app.services import offers

router = APIRouter(prefix="/segments", tags=["segments"])


@router.patch("/{segment_id}")
async def select_segment(
    segment_id: uuid.UUID,
    payload: SegmentSelection,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SegmentRead:
    segment = await offers.set_segment_selected(db, user, segment_id, payload.selected)
    return SegmentRead.model_validate(segment)
