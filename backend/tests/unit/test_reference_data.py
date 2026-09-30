from __future__ import annotations

import typing

import pytest
from pydantic import ValidationError

from app.reference_data import departements, headcount_ranges, naf_codes
from app.schemas.segment import HeadcountRange, SegmentCriteria


def test_reference_lists_are_loaded() -> None:
    assert naf_codes()["62.01Z"]
    assert departements()["75"] == "Paris"
    assert "2A" in departements()
    assert len(headcount_ranges()) == 16


def test_headcount_literal_matches_official_list() -> None:
    assert set(typing.get_args(HeadcountRange)) == set(headcount_ranges())


def _criteria(**overrides: object) -> SegmentCriteria:
    values: dict[str, object] = {
        "naf_codes": ["62.01Z"],
        "headcount_ranges": ["11"],
        "departements": [],
        "keywords": [],
    }
    values.update(overrides)
    return SegmentCriteria.model_validate(values)


def test_valid_criteria_are_normalised() -> None:
    criteria = _criteria(naf_codes=[" 62.01z ", "62.01Z"], departements=["2a"])
    assert criteria.naf_codes == ["62.01Z"]
    assert criteria.departements == ["2A"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"naf_codes": ["99.99Z"]},
        {"naf_codes": ["6201Z"]},
        {"naf_codes": []},
        {"departements": ["00"]},
        {"headcount_ranges": ["99"]},
        {"keywords": ["x" * 61]},
    ],
)
def test_invalid_criteria_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _criteria(**overrides)


def test_demo_data_is_valid() -> None:
    from app.demo.llm_scripts import DEMO_OFFER_PROFILE, DEMO_SEGMENTS

    assert DEMO_OFFER_PROFILE.company_name == "Nimbus Ledger"
    assert len(DEMO_SEGMENTS.segments) == 3
