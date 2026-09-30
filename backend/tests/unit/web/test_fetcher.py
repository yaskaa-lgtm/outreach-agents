"""SafeWebFetcher: SSRF guard, robots.txt, redirects, limits, politeness (HTTP mocked by respx)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.errors import FetchError
from app.providers.web.fetcher import SafeWebFetcher
from app.providers.web.url_safety import UnsafeURLError

HTML_HEADERS = {"content-type": "text/html; charset=utf-8"}
PAGE = b"<html><body><main><p>Example SaaS aide les PME a facturer.</p><a href='/tarifs'>Tarifs</a></main></body></html>"

PUBLIC_DNS = {"example.com": ["93.184.215.14"], "www.example.com": ["93.184.215.14"]}


async def fake_resolver(host: str) -> list[str]:
    return PUBLIC_DNS.get(host, ["10.0.0.7"])  # unknown names resolve to a private address


class FakeTime:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings(
        fetch_max_bytes=2_000,
        fetch_max_redirects=2,
        fetch_min_interval_per_host_seconds=1.0,
    )


def _fetcher(settings: Settings, fake_time: FakeTime | None = None, verify_peer_ip: bool = False) -> SafeWebFetcher:
    fake_time = fake_time or FakeTime()
    return SafeWebFetcher(
        settings,
        resolver=fake_resolver,
        verify_peer_ip=verify_peer_ip,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    )


def _robots(status: int = 404, body: str = "") -> None:
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(status, text=body))


@respx.mock
async def test_fetches_page_with_honest_user_agent(settings: Settings) -> None:
    _robots(404)
    route = respx.get("https://example.com/").mock(return_value=httpx.Response(200, headers=HTML_HEADERS, content=PAGE))
    async with _fetcher(settings) as fetcher:
        page = await fetcher.fetch_page("https://example.com/")
    assert "aide les PME" in page.text
    assert page.links == ["https://example.com/tarifs"]
    assert route.calls.last.request.headers["user-agent"].startswith("outreach-agents-bot/")


@respx.mock
async def test_robots_disallow_is_respected(settings: Settings) -> None:
    _robots(200, "User-agent: *\nDisallow: /private\n")
    page_route = respx.get("https://example.com/private/page")
    async with _fetcher(settings) as fetcher:
        with pytest.raises(FetchError, match="robots.txt"):
            await fetcher.fetch_page("https://example.com/private/page")
    assert not page_route.called


@respx.mock
async def test_robots_server_error_means_disallow(settings: Settings) -> None:
    _robots(503)
    async with _fetcher(settings) as fetcher:
        with pytest.raises(FetchError, match="robots.txt"):
            await fetcher.fetch_page("https://example.com/")


@respx.mock
async def test_redirect_to_private_ip_is_blocked(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/go").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
    )
    async with _fetcher(settings) as fetcher:
        with pytest.raises(UnsafeURLError):
            await fetcher.fetch_page("https://example.com/go")


@respx.mock
async def test_redirect_to_host_resolving_privately_is_blocked(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/go").mock(
        return_value=httpx.Response(302, headers={"location": "https://internal-tools.example.net/"})
    )
    async with _fetcher(settings) as fetcher:
        with pytest.raises(UnsafeURLError, match="private"):
            await fetcher.fetch_page("https://example.com/go")


@respx.mock
async def test_too_many_redirects(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/a").mock(return_value=httpx.Response(302, headers={"location": "/b"}))
    respx.get("https://example.com/b").mock(return_value=httpx.Response(302, headers={"location": "/c"}))
    respx.get("https://example.com/c").mock(return_value=httpx.Response(302, headers={"location": "/a"}))
    async with _fetcher(settings) as fetcher:
        with pytest.raises(FetchError, match="Too many redirects"):
            await fetcher.fetch_page("https://example.com/a")


@respx.mock
async def test_oversized_page_is_rejected(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/big").mock(
        return_value=httpx.Response(200, headers=HTML_HEADERS, content=b"x" * 5_000)
    )
    async with _fetcher(settings) as fetcher:
        with pytest.raises(FetchError, match="too large"):
            await fetcher.fetch_page("https://example.com/big")


@respx.mock
async def test_non_html_content_is_rejected(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/file").mock(
        return_value=httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
    )
    async with _fetcher(settings) as fetcher:
        with pytest.raises(FetchError, match="HTML"):
            await fetcher.fetch_page("https://example.com/file")


@respx.mock
async def test_http_error_status(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/missing").mock(return_value=httpx.Response(404))
    async with _fetcher(settings) as fetcher:
        with pytest.raises(FetchError, match="404"):
            await fetcher.fetch_page("https://example.com/missing")


@respx.mock
async def test_requests_to_the_same_host_are_spaced(settings: Settings) -> None:
    _robots(404)
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, headers=HTML_HEADERS, content=PAGE))
    fake_time = FakeTime()
    async with _fetcher(settings, fake_time) as fetcher:
        await fetcher.fetch_page("https://example.com/")
        await fetcher.fetch_page("https://example.com/")
    assert fake_time.sleeps  # robots.txt, page, page: at least one wait of up to 1 s
    assert all(0 < delay <= 1.0 for delay in fake_time.sleeps)


@respx.mock
async def test_peer_address_check_is_strict(settings: Settings) -> None:
    """Without a verifiable connected address (here: a mocked transport), nothing is read."""
    _robots(404)
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, headers=HTML_HEADERS, content=PAGE))
    async with _fetcher(settings, verify_peer_ip=True) as fetcher:
        with pytest.raises(FetchError):
            await fetcher.fetch_page("https://example.com/")


async def test_unsafe_url_fails_before_any_request(settings: Settings) -> None:
    async with _fetcher(settings) as fetcher:
        with pytest.raises(UnsafeURLError):
            await fetcher.fetch_page("http://127.0.0.1:8000/admin")
