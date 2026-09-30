"""Cost tracking and the daily LLM budget.

Every call is written to `llm_calls` (agent, model, tokens, estimated cost in euros,
duration, success) without any prompt or answer content. Before each call the daily
budget is checked: at 100 % the call is refused with `LLMBudgetExhaustedError`, which
pauses the work instead of failing it. The day follows the Europe/Paris calendar.

Pricing multipliers for prompt caching (reads 0.1x, 5-minute writes 1.25x the base input
price): https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-09-30).
These are the standard multipliers of the default models; a few models have cheaper cache
reads, which this estimate then slightly overestimates (the safe side for a budget).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import LLMBudgetExhaustedError, NotFoundError
from app.models import LLMCall, Workspace
from app.providers.llm.base import (
    LLMClient,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    ModelRole,
    TokenUsage,
)
from app.schemas.budget import WARNING_RATIO, BudgetState, BudgetStatus

logger = logging.getLogger(__name__)

PARIS = ZoneInfo("Europe/Paris")
CACHE_READ_MULTIPLIER = Decimal("0.1")
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
_PER_MILLION = Decimal(1_000_000)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ModelPrice:
    input_usd_per_mtok: Decimal
    output_usd_per_mtok: Decimal


class CostCalculator:
    def __init__(self, prices: Mapping[ModelRole, ModelPrice], usd_to_eur_rate: Decimal) -> None:
        self._prices = dict(prices)
        self._rate = usd_to_eur_rate

    @classmethod
    def free(cls) -> CostCalculator:
        """For the fake LLM: every call costs nothing."""
        zero = ModelPrice(Decimal(0), Decimal(0))
        return cls({ModelRole.REASONING: zero, ModelRole.FAST: zero}, Decimal(0))

    @classmethod
    def from_settings(cls, settings: Settings) -> CostCalculator:
        if settings.demo_mode:
            return cls.free()

        def price(value: float | None) -> Decimal:
            if value is None:
                raise ValueError("LLM prices must be configured outside demo mode")
            return Decimal(str(value))

        rate = settings.usd_to_eur_rate
        if rate is None:
            raise ValueError("USD_TO_EUR_RATE must be configured outside demo mode")
        return cls(
            {
                ModelRole.REASONING: ModelPrice(
                    price(settings.llm_price_reasoning_input_usd_per_mtok),
                    price(settings.llm_price_reasoning_output_usd_per_mtok),
                ),
                ModelRole.FAST: ModelPrice(
                    price(settings.llm_price_fast_input_usd_per_mtok),
                    price(settings.llm_price_fast_output_usd_per_mtok),
                ),
            },
            Decimal(str(rate)),
        )

    def cost_eur(self, role: ModelRole, usage: TokenUsage) -> Decimal:
        price = self._prices[role]
        input_usd = (
            Decimal(usage.input_tokens) * price.input_usd_per_mtok
            + Decimal(usage.cache_read_input_tokens)
            * price.input_usd_per_mtok
            * CACHE_READ_MULTIPLIER
            + Decimal(usage.cache_creation_input_tokens)
            * price.input_usd_per_mtok
            * CACHE_WRITE_MULTIPLIER
        )
        output_usd = Decimal(usage.output_tokens) * price.output_usd_per_mtok
        return ((input_usd + output_usd) / _PER_MILLION * self._rate).quantize(Decimal("0.000001"))


def day_window(now: datetime) -> tuple[datetime, datetime]:
    """Start and end (UTC) of the Europe/Paris calendar day containing `now`."""
    local_day = now.astimezone(PARIS).date()
    start = datetime.combine(local_day, dt_time.min, tzinfo=PARIS)
    end = datetime.combine(local_day + timedelta(days=1), dt_time.min, tzinfo=PARIS)
    return start.astimezone(UTC), end.astimezone(UTC)


async def budget_status(
    session: AsyncSession, workspace_id: uuid.UUID, now: datetime | None = None
) -> BudgetStatus:
    now = now or utc_now()
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFoundError("Workspace not found.")
    start, end = day_window(now)
    spent = await session.scalar(
        select(func.coalesce(func.sum(LLMCall.cost_eur), 0)).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.created_at >= start,
            LLMCall.created_at < end,
        )
    )
    spent_eur = Decimal(spent or 0)
    limit_eur = Decimal(workspace.daily_llm_budget_eur)
    ratio = float(spent_eur / limit_eur) if limit_eur > 0 else 1.0
    state: BudgetState = (
        "exhausted" if ratio >= 1 else "warning" if ratio >= WARNING_RATIO else "ok"
    )
    return BudgetStatus(
        spent_eur=float(spent_eur),
        limit_eur=float(limit_eur),
        ratio=round(ratio, 4),
        state=state,
        resets_at=end,
    )


class MeteredLLMClient:
    """Wraps any `LLMClient`: checks the budget before, records the call after."""

    def __init__(
        self,
        inner: LLMClient,
        sessionmaker: async_sessionmaker[AsyncSession],
        workspace_id: uuid.UUID,
        costs: CostCalculator,
        clock: Clock = utc_now,
    ) -> None:
        self._inner = inner
        self._sessionmaker = sessionmaker
        self._workspace_id = workspace_id
        self._costs = costs
        self._clock = clock

    async def complete(self, request: LLMRequest) -> LLMResponse:
        async with self._sessionmaker() as session:
            status = await budget_status(session, self._workspace_id, self._clock())
        if status.state == "exhausted":
            raise LLMBudgetExhaustedError(
                "Daily LLM budget reached: LLM work is paused until tomorrow, "
                "or until the budget is raised.",
                spent_eur=status.spent_eur,
                limit_eur=status.limit_eur,
                resets_at=status.resets_at.isoformat(),
            )

        started = time.perf_counter()
        try:
            response = await self._inner.complete(request)
        except LLMProviderError as exc:
            await self._record(
                request, self._model_name(request), TokenUsage(), started, None, str(exc)
            )
            raise
        await self._record(
            request, response.model, response.usage, started, response.stop_reason, None
        )
        return response

    def _model_name(self, request: LLMRequest) -> str:
        model_for = getattr(self._inner, "model_for", None)
        try:
            return str(model_for(request.role)) if model_for else "unknown"
        except LLMProviderError:
            return "unknown"

    async def _record(
        self,
        request: LLMRequest,
        model: str,
        usage: TokenUsage,
        started: float,
        stop_reason: str | None,
        error_type: str | None,
    ) -> None:
        call = LLMCall(
            workspace_id=self._workspace_id,
            agent=request.agent,
            model=model[:100],
            model_role=request.role.value,
            prompt_version=request.prompt_version,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens,
            cache_creation_input_tokens=usage.cache_creation_input_tokens,
            cost_eur=self._costs.cost_eur(request.role, usage),
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=error_type is None,
            stop_reason=stop_reason,
            error_type=error_type[:100] if error_type else None,
        )
        # A separate transaction: the call is recorded even if the caller later rolls back.
        async with self._sessionmaker() as session:
            session.add(call)
            await session.commit()
        logger.info(
            "LLM call agent=%s model=%s tokens_in=%d tokens_out=%d cost_eur=%s ok=%s",
            request.agent,
            call.model,
            usage.input_tokens,
            usage.output_tokens,
            call.cost_eur,
            call.success,
        )
