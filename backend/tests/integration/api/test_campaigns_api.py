"""Screen 3 through the API: launch a campaign, run the worker, follow prospects, import a CSV.

Demo mode only: fictional companies (Faker), fictional legal notices, example.com domains.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.demo.site import DEMO_WEBSITE_URL
from app.worker.runner import run_once

pytestmark = pytest.mark.integration

Execute = Callable[..., list[tuple[Any, ...]]]
Maker = async_sessionmaker[AsyncSession]

CSV = (
    "name;siren;website;first_name;last_name;title;email\n"
    "Atelier Exemple;104332184;https://www.atelier.example.org;Jeanne;Exemple;Gérante;"
    "j.exemple@atelier.example.org\n"
    "Boutique Test;732829320;boutique.example.org;Paul;Test;Président;paul.test@webmail.example\n"
    "Bad Siren;123456789;;;;;\n"
)


@pytest.fixture
async def client(demo_client: httpx.AsyncClient, log_in: Any) -> AsyncIterator[httpx.AsyncClient]:
    assert (await log_in(demo_client)).status_code == 200
    yield demo_client


async def _validated_segments(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    analysed = await client.post("/offer-profiles/analyze", json={"website_url": DEMO_WEBSITE_URL})
    profile_id = analysed.json()["id"]
    assert (await client.post(f"/offer-profiles/{profile_id}/validate")).status_code == 200
    generated = await client.post(f"/offer-profiles/{profile_id}/segments")
    segments: list[dict[str, Any]] = generated.json()
    return segments


async def _run_worker(settings: Settings, sessionmaker: Maker) -> int:
    runs = 0
    while await run_once(settings, sessionmaker, "test-worker"):
        runs += 1
    return runs


async def test_full_discovery_flow_in_demo_mode(
    client: httpx.AsyncClient,
    app_settings: Callable[..., Settings],
    sessionmaker: Maker,
    db_execute: Execute,
) -> None:
    segments = await _validated_segments(client)
    created = await client.post(
        "/campaigns", json={"name": "Autumn", "segment_ids": [s["id"] for s in segments]}
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["companies_per_segment"] == 10
    assert campaign["jobs"] == {"pending": 3, "failed": 0}
    assert campaign["counts"] == {}

    runs = await _run_worker(app_settings(), sessionmaker)
    assert runs == 3 + 30  # one discovery job per segment, one processing job per company

    progress = (await client.get(f"/campaigns/{campaign['id']}")).json()
    assert progress["jobs"] == {"pending": 0, "failed": 0}
    assert sum(progress["counts"].values()) == 30
    assert set(progress["counts"]) <= {"contact_found", "email_verified", "excluded"}
    assert progress["counts"].get("email_verified", 0) > 0

    prospects = (await client.get(f"/campaigns/{campaign['id']}/prospects")).json()
    assert len(prospects) == 30
    for row in prospects:
        company, contact = row["company"], row["contact"]
        assert company["website_domain"].endswith(".example.com")
        assert company["domain_status"] in {"confirmed", "unconfirmed"}
        if company["domain_status"] == "confirmed":
            assert company["domain_evidence_url"].endswith("/mentions-legales")
        else:
            assert int(company["siren"]) % 10 == 3  # the demo legal notice omits the SIREN
            assert row["state"] != "email_verified"
        if row["state"] == "email_verified":
            # Only a valid address on the company's confirmed domain is ever sendable.
            assert contact["verification_status"] == "valid"
            assert contact["email"].endswith("@" + company["website_domain"])
        if contact and contact["verification_status"] == "webmail":
            assert row["state"] == "excluded"
            assert "webmail" in row["state_reason"]
        if contact and contact["email"] and contact["email"].startswith("contact@"):
            assert contact["is_generic"] is True

    verified = await client.get(
        f"/campaigns/{campaign['id']}/prospects", params={"state": "email_verified"}
    )
    assert {row["state"] for row in verified.json()} == {"email_verified"}
    first_segment = await client.get(
        f"/campaigns/{campaign['id']}/prospects", params={"segment_id": segments[0]["id"]}
    )
    assert len(first_segment.json()) == 10

    detail = (await client.get(f"/prospects/{verified.json()[0]['id']}")).json()
    assert detail["campaign_id"] == campaign["id"]
    assert [t["to_state"] for t in detail["transitions"]] == [
        "discovered",
        "contact_found",
        "email_verified",
    ]
    assert {t["actor"] for t in detail["transitions"]} == {"system:discovery"}

    # Idempotent: nothing left to do, nothing changes.
    assert await _run_worker(app_settings(), sessionmaker) == 0
    assert db_execute("SELECT count(*) FROM companies")[0][0] == 30
    agents = {row[0] for row in db_execute("SELECT DISTINCT agent FROM llm_calls")}
    assert agents == {"offer_analyst", "icp_strategist"}  # Agents 3-4 never call the LLM
    actions = [row[0] for row in db_execute("SELECT action FROM audit_log ORDER BY created_at")]
    assert actions[-1] == "campaign.created"


async def test_campaigns_need_a_validated_profile(client: httpx.AsyncClient) -> None:
    await client.post("/offer-profiles/analyze", json={"website_url": DEMO_WEBSITE_URL})
    response = await client.post(
        "/campaigns", json={"name": "Too early", "segment_ids": [str(uuid.uuid4())]}
    )
    assert response.status_code == 409


async def test_unknown_resources_are_not_found(client: httpx.AsyncClient) -> None:
    await _validated_segments(client)
    foreign = await client.post(
        "/campaigns", json={"name": "Foreign", "segment_ids": [str(uuid.uuid4())]}
    )
    assert foreign.status_code == 404
    assert (await client.get(f"/campaigns/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"/campaigns/{uuid.uuid4()}/prospects")).status_code == 404
    assert (await client.get(f"/prospects/{uuid.uuid4()}")).status_code == 404


async def test_requested_volume_is_capped(client: httpx.AsyncClient) -> None:
    segments = await _validated_segments(client)
    response = await client.post(
        "/campaigns",
        json={"name": "Big", "segment_ids": [segments[0]["id"]], "companies_per_segment": 500},
    )
    assert response.json()["companies_per_segment"] == 50


async def test_csv_import_applies_the_same_rules(
    client: httpx.AsyncClient,
    app_settings: Callable[..., Settings],
    sessionmaker: Maker,
    db_execute: Execute,
) -> None:
    segments = await _validated_segments(client)
    campaign = (
        await client.post(
            "/campaigns",
            json={"name": "CSV", "segment_ids": [segments[0]["id"]], "companies_per_segment": 1},
        )
    ).json()
    url = f"/campaigns/{campaign['id']}/import"

    imported = await client.post(url, json={"csv": CSV})
    assert imported.status_code == 201, imported.text
    assert imported.json()["imported"] == 2
    assert len(imported.json()["errors"]) == 1
    again = await client.post(url, json={"csv": CSV})
    assert (again.json()["imported"], again.json()["already_in_campaign"]) == (0, 2)
    assert (await client.post(url, json={"csv": "siren\n104332184\n"})).status_code == 422

    await _run_worker(app_settings(), sessionmaker)
    rows = {
        row["company"]["name"]: row
        for row in (await client.get(f"/campaigns/{campaign['id']}/prospects")).json()
    }
    # Not one of the fictional demo sites: the domain cannot be confirmed, so the address
    # stays unverified and the prospect is not sendable.
    atelier = rows["Atelier Exemple"]
    assert atelier["company"]["domain_status"] == "not_found"
    assert atelier["state"] == "contact_found"
    assert atelier["contact"]["verification_status"] == "unverified"
    # A personal webmail address is excluded (B2B only).
    boutique = rows["Boutique Test"]
    assert boutique["state"] == "excluded"
    assert boutique["contact"]["verification_status"] == "webmail"
    # Emails are stored with a hash for deduplication and the suppression list.
    hashes = db_execute("SELECT count(*) FROM contacts WHERE email_hash IS NOT NULL")[0][0]
    assert hashes >= 2
