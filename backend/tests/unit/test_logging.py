from __future__ import annotations

import io
import logging

import pytest

from app.core.logging import (
    EmailMaskingFilter,
    configure_logging,
    mask_email,
    mask_emails_in_text,
)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("jane.doe@example.com", "j***@example.com"),
        ("a@example.org", "a***@example.org"),
        ("not-an-email", "not-an-email"),
        ("@example.com", "@example.com"),
    ],
)
def test_mask_email(address: str, expected: str) -> None:
    assert mask_email(address) == expected


def test_mask_emails_in_text_masks_every_address() -> None:
    text = "Draft for jane.doe@example.com, cc bob@sub.example.org."
    assert mask_emails_in_text(text) == "Draft for j***@example.com, cc b***@sub.example.org."


def test_filter_masks_formatted_arguments() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(EmailMaskingFilter())
    logger = logging.getLogger("tests.masking")
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning("Bounce from %s", "jane.doe@example.com")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert "jane.doe@example.com" not in output
    assert "j***@example.com" in output


def test_configure_logging_protects_existing_handlers() -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler(io.StringIO())
    root.addHandler(handler)
    try:
        configure_logging("INFO")
        configure_logging("INFO")  # idempotent: the filter is added only once
        masking_filters = [f for f in handler.filters if isinstance(f, EmailMaskingFilter)]
        assert len(masking_filters) == 1
    finally:
        root.removeHandler(handler)
