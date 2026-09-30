"""First start: create the workspace and the accounts from the configuration.

- Admin account: from ADMIN_EMAIL / ADMIN_PASSWORD (.env, never committed). An existing
  account is never overwritten.
- Demo account (DEMO_MODE=true only): fake, public credentials documented in the README.
  It is refused at login whenever demo mode is off (app.auth.service).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.service import normalize_email
from app.core.config import Settings
from app.core.logging import mask_email
from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.models import User, Workspace

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password"  # noqa: S105 (fake and public on purpose: demo mode only)


async def _ensure_user(
    db: AsyncSession, workspace: Workspace, email: str, password: str, *, is_demo: bool
) -> None:
    email = normalize_email(email)
    if await db.scalar(select(User).where(User.email == email)) is not None:
        return
    db.add(
        User(
            workspace_id=workspace.id,
            email=email,
            password_hash=hash_password(password),
            role="owner",
            is_demo=is_demo,
        )
    )
    logger.info("Created %s account %s", "demo" if is_demo else "admin", mask_email(email))


async def bootstrap(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    try:
        async with sessionmaker() as db:
            workspace = await db.scalar(select(Workspace).order_by(Workspace.created_at).limit(1))
            if workspace is None:
                workspace = Workspace(
                    name="Default workspace",
                    daily_llm_budget_eur=Decimal(str(settings.daily_llm_budget_eur)),
                )
                db.add(workspace)
                await db.flush()

            if settings.demo_mode:
                await _ensure_user(db, workspace, DEMO_EMAIL, DEMO_PASSWORD, is_demo=True)

            if settings.admin_email and settings.admin_password:
                password = settings.admin_password.get_secret_value()
                if len(password) < MIN_PASSWORD_LENGTH:
                    logger.error(
                        "ADMIN_PASSWORD is too short (minimum %d characters): account not created.",
                        MIN_PASSWORD_LENGTH,
                    )
                else:
                    await _ensure_user(db, workspace, settings.admin_email, password, is_demo=False)
            elif not settings.demo_mode:
                logger.warning(
                    "No admin account configured: set ADMIN_EMAIL and ADMIN_PASSWORD in .env."
                )

            await db.commit()
    except ProgrammingError:
        logger.error(
            "Database schema missing: run "
            "`uv run python -m alembic -c backend/alembic.ini upgrade head`."
        )
    except (SQLAlchemyError, OSError) as exc:
        # The API still starts (and /health reports the database as unavailable).
        logger.error(
            "Database unavailable at start-up (%s): accounts not checked.", type(exc).__name__
        )
