"""FastAPI application factory.

Run locally (from the repository root; keep --reload on Windows, see docs/DECISIONS.md):
    uv run python -m uvicorn app.main:app --reload --reload-dir backend/app
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.auth import router as auth_router
from app.api.budget import router as budget_router
from app.api.health import router as health_router
from app.api.offers import router as offers_router
from app.api.segments import router as segments_router
from app.auth.bootstrap import bootstrap
from app.auth.service import LoginGuard
from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_sessionmaker
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.middleware import (
    OriginCheckMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.offers import AgentServices

logger = logging.getLogger(__name__)


async def _app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):  # pragma: no cover - registered for AppError only
        raise exc
    headers = {}
    retry_after = exc.details.get("retry_after")
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(exc.to_dict(), status_code=exc.status_code, headers=headers)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = create_engine(settings.database_url)
        app.state.sessionmaker = create_sessionmaker(app.state.engine)
        app.state.services = AgentServices.from_settings(settings, app.state.sessionmaker)
        await bootstrap(app.state.sessionmaker, settings)
        missing = settings.missing_llm_settings()
        if missing:
            logger.warning(
                "LLM not configured (missing: %s): agents cannot run.", ", ".join(missing)
            )
        logger.info("API started in %s mode", settings.mode)
        try:
            yield
        finally:
            await app.state.engine.dispose()

    app = FastAPI(title="outreach-agents API", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.login_guard = LoginGuard(settings.login_max_failures, settings.login_lockout_minutes)
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_exception_handler(AppError, _app_error_handler)

    # The last middleware added is the outermost one.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.cors_allow_origins)
    app.add_middleware(RateLimitMiddleware, per_minute=settings.api_rate_limit_per_minute)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(offers_router)
    app.include_router(segments_router)
    app.include_router(budget_router)
    return app


app = create_app()
