"""Wrapping of external content. Web pages and emails are data, never instructions.

The wrapper tags are neutralised inside the content itself, so a page cannot close the
tag early and write text that would look like it comes from outside the page.
"""

from __future__ import annotations

import html
import re

_TAG_NAMES = ("untrusted_web_content", "untrusted_user_description", "offer_profile")
_TAG_PATTERN = re.compile(r"<\s*/?\s*(" + "|".join(_TAG_NAMES) + r")\b", re.IGNORECASE)


def _neutralise(text: str) -> str:
    return _TAG_PATTERN.sub(lambda m: m.group(0).replace("<", "&lt;"), text)


def wrap_web_content(url: str, text: str) -> str:
    return (
        f'<untrusted_web_content source="{html.escape(url, quote=True)}">\n'
        f"{_neutralise(text)}\n"
        "</untrusted_web_content>"
    )


def wrap_user_description(text: str) -> str:
    return f"<untrusted_user_description>\n{_neutralise(text)}\n</untrusted_user_description>"


def wrap_offer_profile(json_text: str) -> str:
    return f"<offer_profile>\n{_neutralise(json_text)}\n</offer_profile>"
