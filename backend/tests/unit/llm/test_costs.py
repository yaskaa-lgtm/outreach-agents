from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.providers.llm.base import ModelRole, TokenUsage
from app.providers.llm.metering import CostCalculator, ModelPrice, day_window


def _calculator() -> CostCalculator:
    return CostCalculator(
        {
            ModelRole.REASONING: ModelPrice(Decimal("2"), Decimal("10")),
            ModelRole.FAST: ModelPrice(Decimal("1"), Decimal("5")),
        },
        usd_to_eur_rate=Decimal("0.9"),
    )


def test_cost_in_euros() -> None:
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    # (2 $ + 10 $) x 0.9 = 10.8 €
    assert _calculator().cost_eur(ModelRole.REASONING, usage) == Decimal("10.8")


def test_cache_tokens_use_the_documented_multipliers() -> None:
    usage = TokenUsage(cache_read_input_tokens=1_000_000, cache_creation_input_tokens=1_000_000)
    # reads 0.1 x 1 $ + writes 1.25 x 1 $ = 1.35 $ -> x 0.9 = 1.215 €
    assert _calculator().cost_eur(ModelRole.FAST, usage) == Decimal("1.215")


def test_fake_llm_is_free() -> None:
    usage = TokenUsage(input_tokens=10_000, output_tokens=10_000)
    assert CostCalculator.free().cost_eur(ModelRole.REASONING, usage) == 0


def test_real_prices_are_required_outside_demo(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(ValueError):
        CostCalculator.from_settings(make_settings(demo_mode=False))
    configured = make_settings(
        demo_mode=False,
        usd_to_eur_rate=0.9,
        llm_price_reasoning_input_usd_per_mtok=2,
        llm_price_reasoning_output_usd_per_mtok=10,
        llm_price_fast_input_usd_per_mtok=1,
        llm_price_fast_output_usd_per_mtok=5,
    )
    calculator = CostCalculator.from_settings(configured)
    assert calculator.cost_eur(ModelRole.FAST, TokenUsage(output_tokens=1_000_000)) == Decimal(
        "4.5"
    )


def test_budget_day_follows_paris_time() -> None:
    # 22:30 UTC on 30 September = 00:30 on 1 October in Paris (UTC+2).
    start, end = day_window(datetime(2026, 9, 30, 22, 30, tzinfo=UTC))
    assert start == datetime(2026, 9, 30, 22, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 1, 22, 0, tzinfo=UTC)


def test_budget_day_handles_daylight_saving_change() -> None:
    # 25 October 2026 lasts 25 hours in Paris (back to UTC+1).
    start, end = day_window(datetime(2026, 10, 25, 12, 0, tzinfo=UTC))
    assert (end - start).total_seconds() == 25 * 3600


def test_missing_llm_settings_lists_what_to_set(make_settings: Callable[..., Settings]) -> None:
    assert make_settings(demo_mode=True).missing_llm_settings() == []
    missing = make_settings(demo_mode=False).missing_llm_settings()
    assert "ANTHROPIC_API_KEY" in missing
    assert "USD_TO_EUR_RATE" in missing
