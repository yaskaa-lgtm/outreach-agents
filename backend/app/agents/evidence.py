"""Anti-hallucination check done in code, not by the LLM.

A claim is kept only if its `source_url` is a page that was really fetched during the run
(or the user's own description) and its `excerpt` really appears in that page's text.
Everything else is removed and reported as a warning.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from app.schemas.offer import USER_DESCRIPTION_SOURCE, OfferProfileData, SourcedClaim

# Typographic quotes and non-breaking spaces compare equal to their plain versions.
# (Code points instead of literal characters, which look like plain quotes in an editor.)
_QUOTES = str.maketrans(
    {
        chr(0x2019): "'",  # right single quotation mark
        chr(0x2018): "'",  # left single quotation mark
        chr(0x201C): '"',  # left double quotation mark
        chr(0x201D): '"',  # right double quotation mark
        chr(0x00AB): '"',  # left guillemet
        chr(0x00BB): '"',  # right guillemet
        chr(0x00A0): " ",  # no-break space
        chr(0x202F): " ",  # narrow no-break space
    }
)
_SPACES = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    return _SPACES.sub(" ", text).strip().casefold()


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), (parts.hostname or "").lower(), path, parts.query, ""))


class SourceIndex:
    """Texts the agent really read, looked up by (normalised) URL."""

    def __init__(self) -> None:
        self._texts: dict[str, str] = {}

    def add(self, url: str, text: str) -> None:
        self._texts[normalize_url(url)] = normalize_for_match(text)

    def add_user_description(self, text: str) -> None:
        self._texts[USER_DESCRIPTION_SOURCE] = normalize_for_match(text)

    def supports(self, claim: SourcedClaim) -> bool:
        key = (
            claim.source_url
            if claim.source_url == USER_DESCRIPTION_SOURCE
            else normalize_url(claim.source_url)
        )
        text = self._texts.get(key)
        return text is not None and normalize_for_match(claim.excerpt) in text


def verify_offer_profile(
    data: OfferProfileData, sources: SourceIndex
) -> tuple[OfferProfileData, list[str]]:
    """Return a copy without unsupported claims, and one warning per removed claim."""
    warnings: list[str] = []

    def keep(field: str, claim: SourcedClaim) -> bool:
        if sources.supports(claim):
            return True
        warnings.append(f"Removed unverifiable claim in '{field}': {claim.claim[:120]}")
        return False

    updates: dict[str, object] = {
        field: [claim for claim in claims if keep(field, claim)]
        for field, claims in data.claim_lists().items()
    }
    if data.value_proposition is not None and not keep("value_proposition", data.value_proposition):
        updates["value_proposition"] = None
    return data.model_copy(update=updates), warnings
