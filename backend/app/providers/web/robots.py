"""robots.txt handling, following RFC 9309 (https://www.rfc-editor.org/rfc/rfc9309):

- 2xx: the rules apply;
- 4xx (including 404): no rules, everything is allowed;
- 5xx or network error: assume everything is disallowed (for a short time).

Parsed files are cached per origin.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.core.errors import FetchError

# (status_code, body) of GET {origin}/robots.txt; raises FetchError on network failure.
RobotsFetcher = Callable[[str], Awaitable[tuple[int, str]]]

ALLOW_TTL_SECONDS = 3600.0
ERROR_TTL_SECONDS = 300.0


@dataclass
class _Entry:
    parser: RobotFileParser | None  # None = allow everything
    disallow_all: bool
    expires_at: float


class RobotsCache:
    def __init__(
        self,
        fetch: RobotsFetcher,
        user_agent_token: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._token = user_agent_token
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    async def is_allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        entry = self._entries.get(origin)
        if entry is None or entry.expires_at <= self._clock():
            entry = await self._load(origin)
            self._entries[origin] = entry
        if entry.disallow_all:
            return False
        if entry.parser is None:
            return True
        return entry.parser.can_fetch(self._token, url)

    async def _load(self, origin: str) -> _Entry:
        now = self._clock()
        try:
            status, body = await self._fetch(f"{origin}/robots.txt")
        except FetchError:
            return _Entry(parser=None, disallow_all=True, expires_at=now + ERROR_TTL_SECONDS)
        if status >= 500:
            return _Entry(parser=None, disallow_all=True, expires_at=now + ERROR_TTL_SECONDS)
        if status >= 400:
            return _Entry(parser=None, disallow_all=False, expires_at=now + ALLOW_TTL_SECONDS)
        parser = RobotFileParser()
        parser.parse(body.splitlines())
        return _Entry(parser=parser, disallow_all=False, expires_at=now + ALLOW_TTL_SECONDS)
