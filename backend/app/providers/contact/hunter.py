"""Hunter API v2 (https://hunter.io/api-documentation/v2, checked 2026-10-01).

- Authentication with the `X-API-KEY` header (the key never appears in URLs or logs).
- `GET /v2/domain-search?domain=` lists the addresses of a domain (`data.emails[]` with
  `value`, `type` personal|generic, `first_name`, `last_name`, `position`,
  `verification.status`); `?company=` returns the company's domain (`data.domain`).
- `GET /v2/email-verifier?email=`: `data.status` is one of valid, invalid, accept_all,
  webmail, disposable, unknown; HTTP 202 means "still in progress, call again".
- Errors: `{"errors": [{"id", "code", "details"}]}`; 429 or 403 when limits are reached.

Every call goes through `provider_calls`: identical requests are answered from the cache
(30 days) and never paid twice, and calls stop when the monthly credit limit is reached.
TODO(verify): the documentation does not state the exact credit cost per endpoint; one
credit per call that returns data is counted here, which may overestimate (the safe side).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProviderCall
from app.providers.contact.base import ContactCandidate, VerificationStatus

BASE_URL = "https://api.hunter.io"
PROVIDER = "hunter"
CACHE_TTL = timedelta(days=30)
KNOWN_STATUSES = {"valid", "invalid", "accept_all", "webmail", "disposable", "unknown"}


class HunterCreditsExhaustedError(RuntimeError):
    pass


class HunterError(RuntimeError):
    pass


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class HunterClient:
    name = PROVIDER

    def __init__(
        self,
        api_key: str,
        sessionmaker: async_sessionmaker[AsyncSession],
        workspace_id: uuid.UUID,
        monthly_credit_limit: int,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._workspace_id = workspace_id
        self._limit = monthly_credit_limit
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            transport=transport,
            timeout=httpx.Timeout(20.0, connect=5.0),
            headers={"X-API-KEY": api_key, "Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- public operations -------------------------------------------------------
    async def find(self, domain: str) -> list[ContactCandidate]:
        data = await self._call("domain-search", {"domain": domain, "limit": 10})
        emails = (data or {}).get("emails") or []
        return [
            ContactCandidate(
                first_name=item.get("first_name"),
                last_name=item.get("last_name"),
                title=item.get("position"),
                email=item.get("value"),
                source=PROVIDER,
                source_url=f"https://{domain}",
                verification_status=_status((item.get("verification") or {}).get("status")),
            )
            for item in emails
            if item.get("value")
        ]

    async def domain_for(self, company_name: str) -> str | None:
        data = await self._call("domain-search", {"company": company_name, "limit": 1})
        domain = (data or {}).get("domain")
        return str(domain).lower() if domain else None

    async def verify(self, email: str) -> VerificationStatus:
        data = await self._call("email-verifier", {"email": email})
        return _status((data or {}).get("status")) or "unknown"

    # --- plumbing ---------------------------------------------------------------------
    async def credits_used_this_month(self, db: AsyncSession) -> int:
        used = await db.scalar(
            select(func.coalesce(func.sum(ProviderCall.credits_used), 0)).where(
                ProviderCall.workspace_id == self._workspace_id,
                ProviderCall.provider == PROVIDER,
                ProviderCall.created_at >= _month_start(datetime.now(UTC)),
            )
        )
        return int(used or 0)

    async def _call(self, operation: str, params: dict[str, Any]) -> dict[str, Any] | None:
        request_hash = hashlib.sha256(
            json.dumps({"op": operation, "params": params}, sort_keys=True).encode()
        ).hexdigest()
        now = datetime.now(UTC)
        async with self._sessionmaker() as db:
            cached = await db.scalar(
                select(ProviderCall)
                .where(
                    ProviderCall.workspace_id == self._workspace_id,
                    ProviderCall.provider == PROVIDER,
                    ProviderCall.operation == operation,
                    ProviderCall.request_hash == request_hash,
                    ProviderCall.status_code == 200,
                    ProviderCall.expires_at > now,
                )
                .order_by(ProviderCall.created_at.desc())
                .limit(1)
            )
            if cached is not None:
                return cached.response
            if await self.credits_used_this_month(db) >= self._limit:
                raise HunterCreditsExhaustedError("Monthly Hunter credit limit reached.")

        status_code, data = await self._request(operation, params)
        credits = 1 if status_code == 200 and data else 0
        async with self._sessionmaker() as db:
            db.add(
                ProviderCall(
                    workspace_id=self._workspace_id,
                    provider=PROVIDER,
                    operation=operation,
                    request_hash=request_hash,
                    status_code=status_code,
                    response=data,
                    credits_used=credits,
                    expires_at=now + CACHE_TTL if status_code == 200 else None,
                )
            )
            await db.commit()
        return data

    async def _request(
        self, operation: str, params: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        for attempt in range(6):
            try:
                response = await self._client.get(f"/v2/{operation}", params=params)
            except httpx.HTTPError as exc:
                raise HunterError(f"Hunter unreachable ({type(exc).__name__}).") from exc
            if response.status_code == 202 or response.status_code == 429:
                # 202: verification still running; 429: rate limited. Wait, then retry.
                await self._sleep(min(2**attempt, 30))
                continue
            if response.status_code == 404:
                return 404, None
            if response.status_code >= 400:
                raise HunterError(f"Hunter answered HTTP {response.status_code}.")
            body = response.json()
            return 200, body.get("data")
        raise HunterError("Hunter did not answer in time.")


def _status(value: Any) -> VerificationStatus | None:
    return str(value) if value in KNOWN_STATUSES else None
