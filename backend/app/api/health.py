"""Health endpoint: is the API up, can it reach the database, which mode is active."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app import __version__
from app.core.config import RunMode, Settings, get_settings
from app.core.database import ping_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    mode: RunMode
    database: Literal["ok", "unavailable"]
    version: str


@router.get("/health")
async def health(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    database_ok = await ping_database(request.app.state.engine)
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        mode=settings.mode,
        database="ok" if database_ok else "unavailable",
        version=__version__,
    )
