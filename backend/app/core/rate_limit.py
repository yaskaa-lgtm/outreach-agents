"""In-memory rate limiters.

Good enough for the single-process, self-hosted MVP. State is lost on restart and not
shared between processes: a shared store (PostgreSQL or Redis) is needed before running
several API replicas.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

Clock = Callable[[], float]


class SlidingWindowLimiter:
    """Allows at most `limit` events per key within `window_seconds`."""

    def __init__(self, limit: int, window_seconds: float, clock: Clock = time.monotonic) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] >= self.window_seconds:
            events.popleft()
        if not events:
            del self._events[key]
            return deque()
        return events

    def is_limited(self, key: str) -> bool:
        return len(self._prune(key, self._clock())) >= self.limit

    def hit(self, key: str) -> None:
        now = self._clock()
        self._prune(key, now)
        self._events[key].append(now)

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest event leaves the window (0 when not limited)."""
        now = self._clock()
        events = self._prune(key, now)
        if len(events) < self.limit:
            return 0
        return max(1, int(self.window_seconds - (now - events[0])) + 1)

    def reset(self, key: str) -> None:
        self._events.pop(key, None)

    def hit_and_check(self, key: str) -> bool:
        """Record one event; return True if the key is now over the limit."""
        if self.is_limited(key):
            return True
        self.hit(key)
        return False
