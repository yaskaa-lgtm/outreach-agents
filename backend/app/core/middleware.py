"""HTTP hardening: security headers, Origin check on unsafe methods, per-client rate limit.

Pure ASGI middlewares (no BaseHTTPMiddleware): cheap and they never buffer bodies.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.rate_limit import SlidingWindowLimiter

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Swagger UI and ReDoc load scripts from a CDN: the strict CSP would break them.
DOCS_PATHS = ("/docs", "/redoc")

_BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
_API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")


async def _send_json(
    send: Send, status: int, body: dict[str, object], headers: Iterable[tuple[bytes, bytes]] = ()
) -> None:
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_BASE_HEADERS)
                if not path.startswith(DOCS_PATHS):
                    headers.append(_API_CSP)
                if path.startswith("/auth"):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class OriginCheckMiddleware:
    """Defence in depth against CSRF: a browser request that changes state must come from
    an allowed origin. Server-to-server calls (the Next.js backend) send no Origin header."""

    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed = {origin.rstrip("/") for origin in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            origin = dict(scope["headers"]).get(b"origin")
            if origin is not None and origin.decode("latin-1").rstrip("/") not in self.allowed:
                await _send_json(
                    send, 403, {"code": "origin_not_allowed", "message": "Origin not allowed."}
                )
                return
        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """At most `per_minute` requests per client address (health checks excluded)."""

    def __init__(self, app: ASGIApp, per_minute: int) -> None:
        self.app = app
        self.limiter = SlidingWindowLimiter(limit=per_minute, window_seconds=60)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != "/health":
            client = scope.get("client")
            key = client[0] if client else "unknown"
            if self.limiter.hit_and_check(key):
                retry_after = str(self.limiter.retry_after(key)).encode()
                await _send_json(
                    send,
                    429,
                    {"code": "rate_limited", "message": "Too many requests."},
                    headers=[(b"retry-after", retry_after)],
                )
                return
        await self.app(scope, receive, send)
