"""A company's website is never guessed: a candidate domain is `confirmed` only when the
company's SIREN (or a SIRET starting with it) is printed on the site — French commercial
websites must show it in their legal notice (mentions légales).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.errors import FetchError
from app.providers.web.fetcher import WebFetcher

LEGAL_PAGE_HINTS = (
    "mentions",
    "legal",
    "legales",
    "informations",
    "cgv",
    "cgu",
    "conditions",
    "a-propos",
    "about",
    "imprint",
)
# Spaces, dots, dashes and (narrow) no-break spaces between digits, as in "123 456 789".
_SEPARATOR_CHARS = r"\s." + chr(0x00A0) + chr(0x202F) + "-"
_DIGIT_SEPARATORS = re.compile(rf"(?<=\d)[{_SEPARATOR_CHARS}]+(?=\d)")


@dataclass(frozen=True)
class DomainCheck:
    status: str  # confirmed | unconfirmed | not_found
    evidence_url: str | None = None


def contains_siren(text: str, siren: str) -> bool:
    """True if `text` shows this SIREN, alone or as the start of a SIRET ("123 456 789 00012")."""
    compact = _DIGIT_SEPARATORS.sub("", text)
    return re.search(rf"(?<!\d){siren}(\d{{5}})?(?!\d)", compact) is not None


async def confirm_domain(
    fetcher: WebFetcher, siren: str, domain: str, max_pages: int
) -> DomainCheck:
    home_url = f"https://{domain}/"
    try:
        home = await fetcher.fetch_page(home_url)
    except FetchError:
        return DomainCheck("not_found")
    if contains_siren(home.text, siren):
        return DomainCheck("confirmed", home.url)

    legal_pages = [
        link for link in home.links if any(hint in link.lower() for hint in LEGAL_PAGE_HINTS)
    ]
    for url in legal_pages[: max(0, max_pages - 1)]:
        try:
            page = await fetcher.fetch_page(url)
        except FetchError:
            continue
        if contains_siren(page.text, siren):
            return DomainCheck("confirmed", page.url)
    return DomainCheck("unconfirmed")
