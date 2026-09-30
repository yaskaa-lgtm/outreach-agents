from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration

Execute = Callable[..., list[tuple[Any, ...]]]
Spend = Callable[..., None]


@pytest.fixture
async def client(demo_client: httpx.AsyncClient, log_in: Any) -> AsyncIterator[httpx.AsyncClient]:
    assert (await log_in(demo_client)).status_code == 200
    yield demo_client


async def test_initial_budget(client: httpx.AsyncClient) -> None:
    body = (await client.get("/budget")).json()
    assert body["spent_eur"] == 0
    assert body["limit_eur"] == 2.0
    assert body["state"] == "ok"


async def test_warning_at_80_percent_then_exhausted(
    client: httpx.AsyncClient, record_spend: Spend
) -> None:
    record_spend(1.7)
    assert (await client.get("/budget")).json()["state"] == "warning"
    record_spend(0.3)
    assert (await client.get("/budget")).json()["state"] == "exhausted"


async def test_yesterday_does_not_count(client: httpx.AsyncClient, record_spend: Spend) -> None:
    record_spend(5.0, when=datetime.now(UTC) - timedelta(days=2))
    assert (await client.get("/budget")).json()["spent_eur"] == 0


async def test_raising_the_budget_is_audited(
    client: httpx.AsyncClient, db_execute: Execute
) -> None:
    body = (await client.put("/budget", json={"daily_limit_eur": 5})).json()
    assert body["limit_eur"] == 5.0
    details = db_execute("SELECT details FROM audit_log WHERE action = 'budget.updated'")[0][0]
    assert details == {"previous_eur": 2.0, "new_eur": 5.0}


@pytest.mark.parametrize("value", [0, -1, 5000])
async def test_invalid_budget_values(client: httpx.AsyncClient, value: float) -> None:
    assert (await client.put("/budget", json={"daily_limit_eur": value})).status_code == 422
