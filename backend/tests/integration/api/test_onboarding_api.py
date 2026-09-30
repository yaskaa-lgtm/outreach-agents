"""Screens 1 and 2 through the API: analyse → edit → validate → segments → selection."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.demo.llm_scripts import build_demo_llm
from app.demo.site import DEMO_WEBSITE_URL, DemoWebFetcher
from app.providers.llm.metering import CostCalculator

pytestmark = pytest.mark.integration

Execute = Callable[..., list[tuple[Any, ...]]]

LIVE_LIKE = {
    "demo_mode": False,
    "admin_email": "owner@example.com",
    "admin_password": "a-long-test-password",
    "anthropic_api_key": "not-a-real-key-for-tests",
    "llm_model_reasoning": "model-reasoning-from-env",
    "llm_model_fast": "model-fast-from-env",
    "llm_price_reasoning_input_usd_per_mtok": 2,
    "llm_price_reasoning_output_usd_per_mtok": 10,
    "llm_price_fast_input_usd_per_mtok": 1,
    "llm_price_fast_output_usd_per_mtok": 5,
    "usd_to_eur_rate": 0.9,
}


@pytest.fixture
async def client(demo_client: httpx.AsyncClient, log_in: Any) -> AsyncIterator[httpx.AsyncClient]:
    assert (await log_in(demo_client)).status_code == 200
    yield demo_client


async def test_full_onboarding_flow_in_demo_mode(
    client: httpx.AsyncClient, db_execute: Execute
) -> None:
    assert (await client.get("/offer-profiles/current")).status_code == 404

    analysed = await client.post("/offer-profiles/analyze", json={"website_url": DEMO_WEBSITE_URL})
    assert analysed.status_code == 201, analysed.text
    profile = analysed.json()
    assert profile["status"] == "draft"
    assert profile["warnings"] == []
    assert len(profile["pages_fetched"]) == 4
    assert profile["data"]["company_name"] == "Nimbus Ledger"
    assert all(
        claim["source_url"].startswith(DEMO_WEBSITE_URL) for claim in profile["data"]["pricing"]
    )

    # Segments need a validated profile.
    too_early = await client.post(f"/offer-profiles/{profile['id']}/segments")
    assert too_early.status_code == 409

    edited_data = profile["data"] | {"summary": "Résumé corrigé à la main."}
    edited = await client.put(f"/offer-profiles/{profile['id']}", json={"data": edited_data})
    assert edited.status_code == 200
    assert edited.json()["data"]["summary"] == "Résumé corrigé à la main."

    validated = await client.post(f"/offer-profiles/{profile['id']}/validate")
    assert validated.json()["status"] == "validated"

    generated = await client.post(f"/offer-profiles/{profile['id']}/segments")
    assert generated.status_code == 201
    segments = generated.json()
    assert len(segments) == 3
    assert segments[0]["fit_score"] >= segments[-1]["fit_score"]
    assert segments[0]["criteria"]["naf_codes"]

    selected = await client.patch(f"/segments/{segments[0]['id']}", json={"selected": True})
    assert selected.json()["selected"] is True
    listed = await client.get(f"/offer-profiles/{profile['id']}/segments")
    assert [s["selected"] for s in listed.json()] == [True, False, False]

    actions = [row[0] for row in db_execute("SELECT action FROM audit_log ORDER BY created_at")]
    assert actions == [
        "auth.login",
        "offer_profile.analyzed",
        "offer_profile.edited",
        "offer_profile.validated",
        "segments.generated",
        "segment.selected",
    ]
    calls = db_execute("SELECT agent, model, cost_eur, success FROM llm_calls")
    assert len(calls) == 6  # 5 turns for Agent 1, 1 for Agent 2
    assert {row[1] for row in calls} == {"fake-llm"}
    assert all(row[2] == 0 and row[3] for row in calls)


async def test_demo_mode_always_analyses_the_fictional_site(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/offer-profiles/analyze", json={"website_url": "https://www.example.org/"}
    )
    assert response.status_code == 201
    assert "Demo mode" in response.json()["warnings"][0]


async def test_analysis_needs_a_url_or_a_description(client: httpx.AsyncClient) -> None:
    response = await client.post("/offer-profiles/analyze", json={})
    assert response.status_code == 422


async def test_editing_rejects_invalid_profiles(client: httpx.AsyncClient) -> None:
    profile = (
        await client.post("/offer-profiles/analyze", json={"website_url": DEMO_WEBSITE_URL})
    ).json()
    broken = profile["data"] | {"summary": ""}
    assert (
        await client.put(f"/offer-profiles/{profile['id']}", json={"data": broken})
    ).status_code == 422


async def test_unknown_or_foreign_resources_are_not_found(
    client: httpx.AsyncClient, db_execute: Execute
) -> None:
    other_workspace = uuid.uuid4()
    other_profile = uuid.uuid4()
    db_execute(
        "INSERT INTO workspaces (id, name, daily_llm_budget_eur) VALUES (%s, 'Other', 2)",
        (other_workspace,),
    )
    db_execute(
        "INSERT INTO offer_profiles (id, workspace_id, data, status, warnings, pages_fetched) "
        "VALUES (%s, %s, '{}', 'validated', '[]', '[]')",
        (other_profile, other_workspace),
    )
    assert (await client.get(f"/offer-profiles/{other_profile}/segments")).status_code == 404
    assert (await client.post(f"/offer-profiles/{other_profile}/validate")).status_code == 404
    assert (
        await client.patch(f"/segments/{uuid.uuid4()}", json={"selected": True})
    ).status_code == 404


async def test_llm_not_configured_is_explicit(
    app_settings: Callable[..., Settings], run_app: Any, log_in: Any
) -> None:
    settings = app_settings(
        demo_mode=False, admin_email="owner@example.com", admin_password="a-long-test-password"
    )
    async with run_app(settings) as (_app, client):
        await log_in(client, "owner@example.com", "a-long-test-password")
        response = await client.post(
            "/offer-profiles/analyze", json={"description": "Nous vendons du café."}
        )
    assert response.status_code == 503
    assert response.json()["code"] == "llm_not_configured"
    assert "ANTHROPIC_API_KEY" in response.json()["details"]["missing"]


async def test_unsafe_url_is_rejected_before_any_llm_call(
    app_settings: Callable[..., Settings], run_app: Any, log_in: Any, db_execute: Execute
) -> None:
    async with run_app(app_settings(**LIVE_LIKE), llm=build_demo_llm()) as (_app, client):
        await log_in(client, "owner@example.com", "a-long-test-password")
        response = await client.post(
            "/offer-profiles/analyze", json={"website_url": "http://169.254.169.254/latest/"}
        )
    assert response.status_code == 422
    assert response.json()["code"] == "unsafe_url"
    assert db_execute("SELECT count(*) FROM llm_calls") == [(0,)]


async def test_budget_exhausted_pauses_llm_work(
    app_settings: Callable[..., Settings],
    run_app: Any,
    log_in: Any,
    db_execute: Execute,
    record_spend: Callable[..., None],
) -> None:
    async with run_app(app_settings(**LIVE_LIKE), llm=build_demo_llm()) as (app, client):
        app.state.services.fetcher_factory = DemoWebFetcher
        await log_in(client, "owner@example.com", "a-long-test-password")
        record_spend(2.5)
        paused = await client.post(
            "/offer-profiles/analyze", json={"website_url": DEMO_WEBSITE_URL}
        )
        assert paused.status_code == 429
        assert paused.json()["code"] == "llm_budget_exhausted"
        assert "resets_at" in paused.json()["details"]

        # Raising the budget resumes the work.
        assert (await client.put("/budget", json={"daily_limit_eur": 10})).json()["state"] == "ok"
        resumed = await client.post(
            "/offer-profiles/analyze", json={"website_url": DEMO_WEBSITE_URL}
        )
    assert resumed.status_code == 201, resumed.text
    costs = db_execute(
        "SELECT cost_eur FROM llm_calls WHERE agent = 'offer_analyst' AND model = 'fake-llm'"
    )
    assert len(costs) == 5
    assert all(row[0] > 0 for row in costs)  # real prices applied to the recorded token counts


def test_costs_are_free_in_demo_mode(make_settings: Callable[..., Settings]) -> None:
    assert CostCalculator.from_settings(make_settings(demo_mode=True)).cost_eur is not None
