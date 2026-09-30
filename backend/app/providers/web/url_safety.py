"""SSRF protection: only public http(s) URLs that resolve to public IP addresses.

Checks happen twice: before connecting (every address the name resolves to must be
public) and after connecting (the address actually connected to must be public), which
defeats DNS rebinding. Redirect targets go through the same checks.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import SplitResult, urlsplit

from app.core.errors import FetchError

Resolver = Callable[[str], Awaitable[list[str]]]

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {None, 80, 443}
BLOCKED_HOSTNAMES = {"localhost"}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".intranet")


class UnsafeURLError(FetchError):
    code = "unsafe_url"


def is_public_ip(value: str) -> bool:
    """True only for globally routable unicast addresses (no private, loopback,
    link-local, carrier-grade NAT, multicast, reserved or unspecified ranges)."""
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


def validate_url(url: str) -> SplitResult:
    """Syntax-level checks. Raises UnsafeURLError with a human-readable reason."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid URL: {url!r}") from exc
    if parts.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed.")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs with credentials are not allowed.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURLError("The URL has no host.")
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError("Only the default ports (80, 443) are allowed.")
    if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_SUFFIXES):
        raise UnsafeURLError("Local host names are not allowed.")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        if "." not in host:
            raise UnsafeURLError("Single-label host names are not allowed.") from None
    else:
        if not is_public_ip(host.strip("[]")):
            raise UnsafeURLError("Private, local or reserved IP addresses are not allowed.")
    return parts


async def system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


async def ensure_public_host(host: str, resolver: Resolver = system_resolver) -> list[str]:
    """Resolve `host`; every address must be public (one private address is enough to refuse)."""
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        return [host.strip("[]")]
    try:
        addresses = await resolver(host)
    except OSError as exc:
        raise FetchError(f"Cannot resolve host {host!r}.") from exc
    if not addresses:
        raise FetchError(f"Cannot resolve host {host!r}.")
    if not all(is_public_ip(address) for address in addresses):
        raise UnsafeURLError(f"Host {host!r} resolves to a private or reserved address.")
    return addresses


def same_site(host_a: str, host_b: str) -> bool:
    """True when both hosts are equal once a leading 'www.' is ignored."""

    def bare(host: str) -> str:
        host = host.lower().rstrip(".")
        return host[4:] if host.startswith("www.") else host

    return bare(host_a) == bare(host_b)
