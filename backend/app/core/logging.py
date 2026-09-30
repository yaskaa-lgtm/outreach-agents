"""Logging setup with personal-data masking.

Rule from docs/SECURITY.md: logs never contain secrets or full email addresses.
Every handler gets `EmailMaskingFilter`, which rewrites `jane.doe@example.com`
into `j***@example.com` before the record is written anywhere.
"""

from __future__ import annotations

import logging
import re
import sys

# Pragmatic address pattern: good enough to catch addresses inside free text.
EMAIL_PATTERN = re.compile(
    r"(?P<local>[A-Za-z0-9._%+\-]+)"  # local part
    r"@(?P<domain>[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"  # domain with a TLD
)

# Loggers created by uvicorn before our code runs; they need the filter too.
_THIRD_PARTY_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def mask_email(address: str) -> str:
    """Mask one email address: keep the first character and the domain."""
    local, sep, domain = address.partition("@")
    if not sep or not local:
        return address
    return f"{local[0]}***@{domain}"


def mask_emails_in_text(text: str) -> str:
    """Mask every email address found in a piece of text."""
    return EMAIL_PATTERN.sub(lambda m: mask_email(m.group(0)), text)


class EmailMaskingFilter(logging.Filter):
    """Masks email addresses in the final log message (after %-formatting)."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        masked = mask_emails_in_text(message)
        if masked != message:
            record.msg = masked
            record.args = None
        return True


def _add_filter_once(handler: logging.Handler) -> None:
    if not any(isinstance(f, EmailMaskingFilter) for f in handler.filters):
        handler.addFilter(EmailMaskingFilter())


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once, and protect third-party handlers as well."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)

    for existing in root.handlers:
        _add_filter_once(existing)
    for name in _THIRD_PARTY_LOGGERS:
        for existing in logging.getLogger(name).handlers:
            _add_filter_once(existing)
