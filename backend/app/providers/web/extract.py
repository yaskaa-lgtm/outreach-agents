"""HTML → clean text (trafilatura, Apache-2.0) and same-site link extraction (lxml)."""

from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlsplit

import lxml.html
import trafilatura
from lxml.etree import ParserError

from app.providers.web.url_safety import same_site

MAX_LINKS = 100
_SKIPPED_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".mp4", ".mp3",
    ".css", ".js", ".xml", ".json", ".ico", ".doc", ".docx", ".xls", ".xlsx",
)  # fmt: skip
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def extract_text(html: bytes, url: str) -> str:
    """Main readable text of the page ('' when nothing useful is found)."""
    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    if not text:
        try:
            text = lxml.html.fromstring(html).text_content()
        except (ParserError, ValueError):
            return ""
    return normalize_text(text or "")


def extract_links(html: bytes, base_url: str) -> list[str]:
    """Absolute http(s) links to pages of the same site, deduplicated, in page order."""
    try:
        document = lxml.html.fromstring(html)
    except (ParserError, ValueError):
        return []
    base_host = urlsplit(base_url).hostname or ""
    links: dict[str, None] = {}
    for href in document.xpath("//a/@href"):
        absolute, _fragment = urldefrag(urljoin(base_url, str(href).strip()))
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        if not same_site(parts.hostname, base_host):
            continue
        if parts.path.lower().endswith(_SKIPPED_EXTENSIONS):
            continue
        links.setdefault(absolute, None)
        if len(links) >= MAX_LINKS:
            break
    return list(links)
