"""No strong-copyleft dependency (GPL, AGPL) in the Python environment.

Weak copyleft (LGPL, MPL) is only accepted for packages listed below, each documented in
docs/DECISIONS.md ("Dependencies and licences").
"""

from __future__ import annotations

import re
from importlib.metadata import Distribution, distributions

# name -> reason (keep in sync with docs/DECISIONS.md)
REVIEWED_WEAK_COPYLEFT = {
    "psycopg": "LGPL-3.0, used unmodified as a library",
    "psycopg-binary": "LGPL-3.0, binary build of psycopg",
    "certifi": "MPL-2.0, CA bundle used unmodified",
    "pathspec": "MPL-2.0, development tool dependency",
    "tld": "triple licence MPL-1.1 / GPL-2.0 / LGPL-2.1: used under MPL-1.1",
}

_STRONG_COPYLEFT = re.compile(r"(?<![L])\bA?GPL|General Public License(?! v?\d? ?\(?LGPL)")


def _licence(distribution: Distribution) -> str:
    metadata = distribution.metadata
    expression = metadata.get("License-Expression")
    if expression:
        return str(expression)
    classifiers = [c for c in metadata.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return " | ".join(classifiers)
    return str(metadata.get("License") or "UNKNOWN").splitlines()[0]


def _is_weak_or_strong_copyleft(licence: str) -> bool:
    upper = licence.upper()
    return "GPL" in upper or "GENERAL PUBLIC" in upper or "MPL" in upper or "MOZILLA" in upper


def test_no_unreviewed_copyleft_dependency() -> None:
    offenders = []
    for distribution in distributions():
        name = str(distribution.metadata["Name"]).lower()
        licence = _licence(distribution)
        if _is_weak_or_strong_copyleft(licence) and name not in REVIEWED_WEAK_COPYLEFT:
            offenders.append(f"{name}: {licence}")
    assert offenders == [], "Review these licences and document them in docs/DECISIONS.md"


def test_reviewed_packages_are_not_strong_copyleft_only() -> None:
    for distribution in distributions():
        name = str(distribution.metadata["Name"]).lower()
        if name in REVIEWED_WEAK_COPYLEFT and name != "tld":
            licence = _licence(distribution).upper()
            assert "AGPL" not in licence
            assert not _STRONG_COPYLEFT.search(licence.replace("LGPL", "").replace("LESSER", "")), (
                name
            )
