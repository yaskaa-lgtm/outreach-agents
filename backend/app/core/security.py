"""Password hashing and session tokens.

- Passwords: argon2id through `pwdlib` (https://frankie567.github.io/pwdlib/).
- Session tokens: 256 random bits; only their SHA-256 hash is stored in the database,
  so a database leak does not leak usable sessions.
"""

from __future__ import annotations

import hashlib
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()

# Verified against when the email is unknown, so that response time does not reveal
# whether an account exists.
_DUMMY_HASH = _password_hash.hash("dummy-password-for-constant-time-checks")

MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time check; `password_hash=None` still spends the same effort."""
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
