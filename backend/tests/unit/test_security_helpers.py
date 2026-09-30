from __future__ import annotations

from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import hash_password, hash_token, new_session_token, verify_password


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_unknown_user_check_still_returns_false() -> None:
    assert verify_password("anything", None) is False


def test_session_tokens_are_random_and_stored_hashed() -> None:
    first, second = new_session_token(), new_session_token()
    assert first != second
    assert len(first) >= 40
    assert hash_token(first) != first
    assert len(hash_token(first)) == 64


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_limits_then_recovers() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=clock)
    assert not limiter.hit_and_check("k")
    assert not limiter.hit_and_check("k")
    assert limiter.hit_and_check("k")
    assert limiter.retry_after("k") > 0
    clock.now += 61
    assert not limiter.is_limited("k")
    assert limiter.retry_after("k") == 0


def test_sliding_window_reset() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    limiter.hit("k")
    assert limiter.is_limited("k")
    limiter.reset("k")
    assert not limiter.is_limited("k")
