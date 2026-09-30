"""Daily LLM budget: 80 % = warning, 100 % = LLM work paused until the next day."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BudgetState = Literal["ok", "warning", "exhausted"]
WARNING_RATIO = 0.8


class BudgetStatus(BaseModel):
    spent_eur: float
    limit_eur: float
    ratio: float
    state: BudgetState
    resets_at: datetime


class BudgetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_limit_eur: float = Field(gt=0, le=1000)
