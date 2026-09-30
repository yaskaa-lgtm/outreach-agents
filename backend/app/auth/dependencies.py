"""FastAPI dependency: the logged-in user, from the session cookie."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.service import AuthenticatedUser, resolve_session
from app.core.config import Settings
from app.core.errors import AuthenticationError


async def current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> AuthenticatedUser:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthenticationError("Please log in.")
    user = await resolve_session(db, token, demo_accounts_enabled=settings.demo_mode)
    if user is None:
        raise AuthenticationError("Your session has expired. Please log in again.")
    return user


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]
