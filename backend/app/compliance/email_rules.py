"""Email address rules shared by discovery and (later) sending.

- Personal webmail domains are never prospected (B2B only).
- Generic role addresses (contact@, info@...) are accepted but flagged.
- Only the `valid` verification status is sendable (validated decision, docs/PLAN.md).
- The SHA-256 of the normalised address identifies a person without storing the address
  twice (de-duplication now, suppression list in Phase 4).
"""

from __future__ import annotations

import hashlib
import re
from functools import cache
from importlib.resources import files

SENDABLE_STATUSES = frozenset({"valid"})
NEVER_SENDABLE_STATUSES = frozenset({"invalid", "webmail", "disposable"})

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")

GENERIC_LOCAL_PARTS = frozenset(
    {
        "accueil", "admin", "administration", "bonjour", "commercial", "compta",
        "comptabilite", "contact", "direction", "equipe", "facturation", "hello",
        "info", "infos", "jobs", "marketing", "office", "recrutement", "rh",
        "sales", "secretariat", "service", "serviceclient", "support", "team", "vente",
    }
)  # fmt: skip


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_syntax(email: str) -> bool:
    return bool(_EMAIL.match(normalize_email(email)))


def email_domain(email: str) -> str:
    return normalize_email(email).rsplit("@", 1)[-1]


def email_hash(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


@cache
def webmail_domains() -> frozenset[str]:
    text = files(__package__).joinpath("webmail_domains.txt").read_text(encoding="utf-8")
    return frozenset(
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    )


def is_webmail(email: str) -> bool:
    return email_domain(email) in webmail_domains()


def is_generic(email: str) -> bool:
    local = normalize_email(email).split("@", 1)[0]
    return local.replace("-", "").replace(".", "").replace("_", "") in GENERIC_LOCAL_PARTS
