"""The only way agents read the web: `WebFetcher.fetch_page()`.

Safety rules (docs/SECURITY.md):
- SSRF: public http(s) URLs only, checked before connecting and on the connected peer
  address; redirects (at most `fetch_max_redirects`) are re-checked hop by hop.
- Limits: response size (`fetch_max_bytes`), time (`fetch_timeout_seconds`), HTML or text only.
- Politeness: robots.txt (RFC 9309), an honest User-Agent, one request per host per
  `fetch_min_interval_per_host_seconds`.
- No proxy from the environment (`trust_env=False`): it would bypass the peer check.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, Self
from urllib.parse import urljoin

import httpx

from app.core.config import Settings
from app.core.errors import FetchError
from app.providers.web.extract import extract_links, extract_text
from app.providers.web.robots import RobotsCache
from app.providers.web.url_safety import (
    Resolver,
    UnsafeURLError,
    ensure_public_host,
    is_public_ip,
    system_resolver,
    validate_url,
)

HTML_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
ROBOTS_MAX_BYTES = 500_000


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    url: str  # final URL after redirects
    text: str
    links: list[str]
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WebFetcher(Protocol):
    async def fetch_page(self, url: str) -> FetchedPage: ...


class _HostThrottle:
    def __init__(self, min_interval: float, clock: Callable[[], float], sleep: Callable[[float], Awaitable[None]]) -> None:
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            last = self._last.get(host)
            if last is not None:
                delay = self._min_interval - (self._clock() - last)
                if delay > 0:
                    await self._sleep(delay)
            self._last[host] = self._clock()


class SafeWebFetcher:
    """Use as an async context manager: `async with SafeWebFetcher(settings) as fetcher:`."""

    def __init__(
        self,
        settings: Settings,
        *,
        resolver: Resolver = system_resolver,
        transport: httpx.AsyncBaseTransport | None = None,
        verify_peer_ip: bool = True,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._resolver = resolver
        self._verify_peer_ip = verify_peer_ip
        self._client = httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(settings.fetch_timeout_seconds, connect=5.0),
            headers={
                "User-Agent": settings.bot_user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
            },
        )
        self._throttle = _HostThrottle(settings.fetch_min_interval_per_host_seconds, clock, sleep)
        self._robots = RobotsCache(self._fetch_robots, settings.bot_robots_name, clock)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.aclose()

    async def fetch_page(self, url: str) -> FetchedPage:
        final_url, body = await self._get(url, check_robots=True, max_bytes=self._settings.fetch_max_bytes)
        text = await asyncio.to_thread(extract_text, body, final_url)
        links = extract_links(body, final_url)
        return FetchedPage(requested_url=url, url=final_url, text=text, links=links)

    async def _fetch_robots(self, robots_url: str) -> tuple[int, str]:
        try:
            _final, body = await self._get(robots_url, check_robots=False, max_bytes=ROBOTS_MAX_BYTES, any_status=True)
        except _HTTPStatusError as exc:
            return exc.status_code, ""
        return 200, body.decode("utf-8", errors="replace")

    async def _get(
        self, url: str, *, check_robots: bool, max_bytes: int, any_status: bool = False
    ) -> tuple[str, bytes]:
        current = url
        for _hop in range(self._settings.fetch_max_redirects + 1):
            parts = validate_url(current)
            host = parts.hostname or ""
            await ensure_public_host(host, self._resolver)
            if check_robots and not await self._robots.is_allowed(current):
                raise FetchError(f"robots.txt of {host} does not allow fetching this page.", url=current)
            await self._throttle.wait(host)
            try:
                async with asyncio.timeout(self._settings.fetch_timeout_seconds):
                    async with self._client.stream("GET", current) as response:
                        self._check_peer(response, host)
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise FetchError("Redirect without a Location header.", url=current)
                            current = urljoin(current, location)
                            continue
                        if response.status_code >= 400:
                            raise _HTTPStatusError(response.status_code, current)
                        if not any_status:
                            content_type = response.headers.get("content-type", "").lower()
                            if not content_type.startswith(HTML_TYPES):
                                raise FetchError("Only HTML or text pages can be read.", url=current)
                        body = await self._read_limited(response, max_bytes)
                        return str(response.url), body
            except TimeoutError as exc:
                raise FetchError("The page took too long to answer.", url=current) from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Network error ({type(exc).__name__}).", url=current) from exc
        raise FetchError("Too many redirects.", url=url)

    def _check_peer(self, response: httpx.Response, host: str) -> None:
        if not self._verify_peer_ip:
            return
        stream = response.extensions.get("network_stream")
        peer = stream.get_extra_info("server_addr") if stream is not None else None
        if not peer or not is_public_ip(str(peer[0])):
            raise UnsafeURLError(f"Connection to {host!r} reached a non-public address.")

    @staticmethod
    async def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise FetchError("The page is too large.", max_bytes=max_bytes)
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise FetchError("The page is too large.", max_bytes=max_bytes)
            chunks.append(chunk)
        return b"".join(chunks)


class _HTTPStatusError(FetchError):
    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"The page answered with HTTP {status_code}.", url=url)
        self.status_code = status_code
