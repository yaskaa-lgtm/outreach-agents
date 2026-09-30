from __future__ import annotations

import pytest

from app.core.errors import FetchError
from app.providers.web.url_safety import (
    UnsafeURLError,
    ensure_public_host,
    is_public_ip,
    same_site,
    validate_url,
)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("93.184.215.14", True),
        ("2606:4700::6810:84e5", True),
        ("127.0.0.1", False),
        ("10.0.0.5", False),
        ("172.16.3.4", False),
        ("192.168.1.10", False),
        ("169.254.169.254", False),  # cloud metadata endpoint
        ("100.64.0.1", False),  # carrier-grade NAT
        ("0.0.0.0", False),
        ("::1", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("::ffff:127.0.0.1", False),  # IPv4-mapped loopback
        ("224.0.0.1", False),
        ("not-an-ip", False),
    ],
)
def test_is_public_ip(address: str, expected: bool) -> None:
    assert is_public_ip(address) is expected


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "http://localhost/",
        "http://printer.local/",
        "http://intranet/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://example.com:8080/",
        "https:///nohost",
    ],
)
def test_unsafe_urls_are_rejected(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        validate_url(url)


def test_public_url_is_accepted() -> None:
    parts = validate_url("https://www.example.com/about")
    assert parts.hostname == "www.example.com"


async def test_host_resolving_to_a_private_address_is_rejected() -> None:
    async def resolver(_host: str) -> list[str]:
        return ["203.0.113.10", "10.0.0.1"]  # one private address is enough

    with pytest.raises(UnsafeURLError):
        await ensure_public_host("rebind.example.com", resolver)


async def test_host_resolving_to_public_addresses_is_accepted() -> None:
    async def resolver(_host: str) -> list[str]:
        return ["93.184.215.14"]

    assert await ensure_public_host("example.com", resolver) == ["93.184.215.14"]


async def test_unresolvable_host() -> None:
    async def resolver(_host: str) -> list[str]:
        raise OSError("no such host")

    with pytest.raises(FetchError):
        await ensure_public_host("nope.example.com", resolver)


def test_same_site_ignores_www() -> None:
    assert same_site("www.example.com", "example.com")
    assert not same_site("evil-example.com", "example.com")
