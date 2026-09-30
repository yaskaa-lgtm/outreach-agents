"""Daily LLM budget: read it, or raise it to resume paused LLM work."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import CurrentUser
from app.core.errors import NotFoundError
from app.models import Workspace
from app.providers.llm.metering import budget_status
from app.schemas.budget import BudgetStatus, BudgetUpdate
from app.services import audit

router = APIRouter(prefix="/budget", tags=["budget"])

Db = Annotated[AsyncSession, Depends(get_db)]


@router.get("")
async def get_budget(user: CurrentUser, db: Db) -> BudgetStatus:
    return await budget_status(db, user.workspace_id)


@router.put("")
async def update_budget(payload: BudgetUpdate, user: CurrentUser, db: Db) -> BudgetStatus:
    workspace = await db.get(Workspace, user.workspace_id)
    if workspace is None:
        raise NotFoundError("Workspace not found.")
    previous = float(workspace.daily_llm_budget_eur)
    workspace.daily_llm_budget_eur = Decimal(str(payload.daily_limit_eur)).quantize(Decimal("0.01"))
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_id=user.id,
        action="budget.updated",
        entity_type="workspace",
        entity_id=workspace.id,
        details={"previous_eur": previous, "new_eur": float(workspace.daily_llm_budget_eur)},
    )
    await db.commit()
    return await budget_status(db, user.workspace_id)
