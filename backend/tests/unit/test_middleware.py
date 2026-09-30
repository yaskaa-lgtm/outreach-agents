from __future__ import annotations

import httpx
from fastapi import FastAPI

from app.core.middleware import (
    OriginCheckMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


def _app(per_minute: int = 100) -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/ping")
    async def ping_post() -> dict[str, str]:
        return {"ok": "yes"}

    app.add_middleware(OriginCheckMiddleware, allowed_origins=["http://localhost:3000"])
    app.add_middleware(RateLimitMiddleware, per_minute=per_minute)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_security_headers_are_set() -> None:
    async with _client(_app()) as client:
        response = await client.get("/ping")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]


async def test_unsafe_request_from_foreign_origin_is_refused() -> None:
    async with _client(_app()) as client:
        refused = await client.post("/ping", headers={"Origin": "https://evil.example.com"})
        allowed = await client.post("/ping", headers={"Origin": "http://localhost:3000"})
        server_to_server = await client.post("/ping")
    assert refused.status_code == 403
    assert refused.json()["code"] == "origin_not_allowed"
    assert allowed.status_code == 200
    assert server_to_server.status_code == 200


async def test_rate_limit_answers_429_with_retry_after() -> None:
    async with _client(_app(per_minute=2)) as client:
        codes = [(await client.get("/ping")).status_code for _ in range(3)]
        limited = await client.get("/ping")
    assert codes[:2] == [200, 200]
    assert codes[2] == 429
    assert int(limited.headers["retry-after"]) > 0
