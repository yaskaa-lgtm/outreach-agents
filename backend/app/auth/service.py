"""Login, sessions and brute-force protection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import hash_token, new_session_token, verify_password
from app.models import User, UserSession


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    role: str
    is_demo: bool


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_authenticated(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        role=user.role,
        is_demo=user.is_demo,
    )


async def authenticate(
    db: AsyncSession, email: str, password: str, *, demo_accounts_enabled: bool
) -> AuthenticatedUser | None:
    user = await db.scalar(select(User).where(User.email == normalize_email(email)))
    # Always run the password check (even for unknown users) to keep timing uniform.
    valid = verify_password(password, user.password_hash if user else None)
    if user is None or not valid:
        return None
    # The demo account has public credentials: it must never work outside demo mode.
    if user.is_demo and not demo_accounts_enabled:
        return None
    user.last_login_at = datetime.now(UTC)
    return _to_authenticated(user)


async def open_session(
    db: AsyncSession, user: AuthenticatedUser, ttl_hours: int
) -> tuple[str, datetime]:
    token = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)
    db.add(
        UserSession(
            workspace_id=user.workspace_id,
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    return token, expires_at


async def resolve_session(
    db: AsyncSession, token: str, *, demo_accounts_enabled: bool
) -> AuthenticatedUser | None:
    row = await db.execute(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    user = row.scalar_one_or_none()
    if user is None or (user.is_demo and not demo_accounts_enabled):
        return None
    return _to_authenticated(user)


async def close_session(db: AsyncSession, token: str) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.token_hash == hash_token(token), UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


class LoginGuard:
    """Locks an email address (and a client address) after too many failed logins."""

    def __init__(self, max_failures: int, lockout_minutes: int) -> None:
        window = lockout_minutes * 60
        self._by_email = SlidingWindowLimiter(max_failures, window)
        # A client may try several addresses: a looser limit per client address.
        self._by_client = SlidingWindowLimiter(max_failures * 4, window)

    def retry_after(self, email: str, client: str) -> int:
        email = normalize_email(email)
        return max(self._by_email.retry_after(email), self._by_client.retry_after(client))

    def record_failure(self, email: str, client: str) -> None:
        self._by_email.hit(normalize_email(email))
        self._by_client.hit(client)

    def record_success(self, email: str) -> None:
        self._by_email.reset(normalize_email(email))
