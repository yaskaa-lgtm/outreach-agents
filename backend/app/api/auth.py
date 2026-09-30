"""Login / logout / current user. The session token travels in an HttpOnly cookie."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_address, get_db
from app.auth.dependencies import CurrentUser
from app.auth.service import authenticate, close_session, open_session
from app.core.config import Settings
from app.core.errors import AuthenticationError, TooManyAttemptsError
from app.core.logging import mask_email
from app.schemas.auth import LoginRequest, UserRead
from app.services import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    settings: Settings = request.app.state.settings
    guard = request.app.state.login_guard
    client = client_address(request)

    retry_after = guard.retry_after(payload.email, client)
    if retry_after:
        raise TooManyAttemptsError(
            "Too many failed attempts. Try again later.", retry_after=retry_after
        )

    user = await authenticate(
        db, payload.email, payload.password, demo_accounts_enabled=settings.demo_mode
    )
    if user is None:
        guard.record_failure(payload.email, client)
        logger.info("Failed login for %s", mask_email(payload.email))
        raise AuthenticationError("Invalid email or password.")

    guard.record_success(payload.email)
    token, expires_at = await open_session(db, user, settings.session_ttl_hours)
    audit.record(db, workspace_id=user.workspace_id, actor_id=user.id, action="auth.login")
    await db.commit()

    response.set_cookie(
        settings.session_cookie_name,
        token,
        expires=expires_at,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return UserRead(email=user.email, role=user.role, is_demo=user.is_demo)


@router.post("/logout", status_code=204)
async def logout(
    user: CurrentUser,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name, "")
    await close_session(db, token)
    audit.record(db, workspace_id=user.workspace_id, actor_id=user.id, action="auth.logout")
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me")
async def me(user: CurrentUser) -> UserRead:
    return UserRead(email=user.email, role=user.role, is_demo=user.is_demo)
