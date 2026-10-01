"""Hunter client: header authentication, provider_calls cache, monthly credit limit, retries.

HTTP is mocked with respx; the key is a fake placeholder and every address is synthetic.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProviderCall
from app.providers.contact.hunter import (
    BASE_URL,
    HunterClient,
    HunterCreditsExhaustedError,
    HunterError,
)

pytestmark = pytest.mark.integration

Maker = async_sessionmaker[AsyncSession]
FAKE_KEY = "fake-hunter-key-for-tests"
DOMAIN_SEARCH = f"{BASE_URL}/v2/domain-search"
VERIFIER = f"{BASE_URL}/v2/email-verifier"


async def _no_sleep(_seconds: float) -> None:
    return None


def _client(sessionmaker: Maker, workspace_id: uuid.UUID, limit: int = 50) -> HunterClient:
    return HunterClient(FAKE_KEY, sessionmaker, workspace_id, limit, sleep=_no_sleep)


DOMAIN_RESULT = {
    "data": {
        "domain": "acme.example.com",
        "emails": [
            {
                "value": "j.exemple@acme.example.com",
                "type": "personal",
                "first_name": "Jeanne",
                "last_name": "Exemple",
                "position": "Directrice financière",
                "verification": {"status": "valid"},
            },
            {"value": "contact@acme.example.com", "type": "generic", "verification": None},
            {"type": "personal"},  # no address: ignored
        ],
    }
}


@respx.mock
async def test_find_authenticates_with_a_header_and_maps_contacts(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    route = respx.get(DOMAIN_SEARCH).mock(return_value=httpx.Response(200, json=DOMAIN_RESULT))
    client = _client(sessionmaker, workspace_id)
    try:
        contacts = await client.find("acme.example.com")
    finally:
        await client.aclose()

    request = route.calls.last.request
    assert request.headers["x-api-key"] == FAKE_KEY
    assert FAKE_KEY not in str(request.url)
    assert request.url.params["domain"] == "acme.example.com"
    assert [c.email for c in contacts] == [
        "j.exemple@acme.example.com",
        "contact@acme.example.com",
    ]
    assert contacts[0].title == "Directrice financière"
    assert contacts[0].verification_status == "valid"
    assert contacts[1].verification_status is None
    assert {c.source for c in contacts} == {"hunter"}


@respx.mock
async def test_identical_requests_are_answered_from_the_cache(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    route = respx.get(DOMAIN_SEARCH).mock(return_value=httpx.Response(200, json=DOMAIN_RESULT))
    client = _client(sessionmaker, workspace_id)
    try:
        first = await client.find("acme.example.com")
        second = await client.find("acme.example.com")
        async with sessionmaker() as db:
            assert await client.credits_used_this_month(db) == 1
    finally:
        await client.aclose()
    assert first == second
    assert route.call_count == 1


@respx.mock
async def test_calls_stop_at_the_monthly_credit_limit(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    route = respx.get(VERIFIER).mock(
        return_value=httpx.Response(200, json={"data": {"status": "valid"}})
    )
    client = _client(sessionmaker, workspace_id, limit=1)
    try:
        assert await client.verify("a@acme.example.com") == "valid"
        with pytest.raises(HunterCreditsExhaustedError):
            await client.verify("b@acme.example.com")
        # Already paid for: still answered from the cache.
        assert await client.verify("a@acme.example.com") == "valid"
    finally:
        await client.aclose()
    assert route.call_count == 1


@respx.mock
async def test_verification_in_progress_is_polled_again(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    route = respx.get(VERIFIER).mock(
        side_effect=[
            httpx.Response(202, json={"data": None}),
            httpx.Response(200, json={"data": {"status": "accept_all"}}),
        ]
    )
    client = _client(sessionmaker, workspace_id)
    try:
        assert await client.verify("a@acme.example.com") == "accept_all"
    finally:
        await client.aclose()
    assert route.call_count == 2


@respx.mock
async def test_unknown_statuses_and_missing_results_are_safe(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    respx.get(VERIFIER).mock(
        return_value=httpx.Response(200, json={"data": {"status": "something-new"}})
    )
    respx.get(DOMAIN_SEARCH).mock(return_value=httpx.Response(404, json={"errors": []}))
    client = _client(sessionmaker, workspace_id)
    try:
        assert await client.verify("a@acme.example.com") == "unknown"
        assert await client.domain_for("Acme Exemple") is None
    finally:
        await client.aclose()
    async with sessionmaker() as db:
        missing = await db.scalar(select(ProviderCall).where(ProviderCall.status_code == 404))
    assert missing is not None and missing.credits_used == 0 and missing.expires_at is None


@respx.mock
async def test_domain_for_returns_the_company_domain(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    route = respx.get(DOMAIN_SEARCH).mock(
        return_value=httpx.Response(
            200, json={"data": {"domain": "ACME.example.com", "emails": []}}
        )
    )
    client = _client(sessionmaker, workspace_id)
    try:
        assert await client.domain_for("Acme Exemple") == "acme.example.com"
    finally:
        await client.aclose()
    assert route.calls.last.request.url.params["company"] == "Acme Exemple"


@respx.mock
async def test_server_errors_raise_without_leaking_the_key(
    sessionmaker: Maker, workspace_id: uuid.UUID
) -> None:
    respx.get(VERIFIER).mock(return_value=httpx.Response(401, json={"errors": []}))
    client = _client(sessionmaker, workspace_id)
    try:
        with pytest.raises(HunterError) as error:
            await client.verify("a@acme.example.com")
    finally:
        await client.aclose()
    assert "401" in str(error.value)
    assert FAKE_KEY not in str(error.value)
