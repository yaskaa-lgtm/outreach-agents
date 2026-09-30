"""Official French reference lists (see README.md in this folder for sources and licence)."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files


def _load(name: str) -> dict[str, str]:
    raw = files(__package__).joinpath(name).read_text(encoding="utf-8")
    data: dict[str, str] = json.loads(raw)
    return data


@cache
def naf_codes() -> dict[str, str]:
    """NAF rév. 2 sub-classes, e.g. {"62.01Z": "Programmation informatique"}."""
    return _load("naf_codes.json")


@cache
def departements() -> dict[str, str]:
    """French département codes, e.g. {"75": "Paris", "2A": "Corse-du-Sud"}."""
    return _load("departements.json")


@cache
def headcount_ranges() -> dict[str, str]:
    """INSEE headcount ranges (tranches d'effectif salarié), e.g. {"11": "10 à 19 salariés"}."""
    return _load("headcount_ranges.json")
