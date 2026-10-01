"""Official company registry client (HTTP mocked with respx, synthetic data only)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.errors import FetchError
from app.providers.company.registry import BASE_URL, RegistryCompanyProvider
from app.schemas.segment import SegmentCriteria

CRITERIA = SegmentCriteria(
    naf_codes=["62.01Z", "62.02A"], headcount_ranges=["11", "12"], departements=["69"], keywords=[]
)


def _result(siren: str, officers: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "siren": siren,
        "nom_complet": f"ENTREPRISE EXEMPLE {siren}",
        "activite_principale": "62.01Z",
        "tranche_effectif_salarie": "11",
        "siege": {"code_postal": "69001", "libelle_commune": "LYON", "departement": "69"},
        "complements": {"est_entrepreneur_individuel": False},
        "dirigeants": officers or [],
    }


async def _sleep(_seconds: float) -> None:
    return None


@pytest.fixture
def provider(make_settings: Callable[..., Settings]) -> RegistryCompanyProvider:
    return RegistryCompanyProvider(make_settings(registry_min_interval_seconds=0), sleep=_sleep)


@respx.mock
async def test_search_sends_official_filters_and_keeps_minimal_officer_data(
    provider: RegistryCompanyProvider,
) -> None:
    route = respx.get(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _result(
                        "104332184",
                        [
                            {
                                "nom": "EXEMPLE",
                                "prenoms": "Jeanne",
                                "qualite": "Présidente",
                                "annee_de_naissance": "1970",
                                "nationalite": "Française",
                                "type_dirigeant": "personne physique",
                            },
                            {
                                "siren": "000000000",
                                "denomination": "HOLDING",
                                "type_dirigeant": "personne morale",
                            },
                        ],
                    ),
                    _result("123456789"),  # invalid checksum: ignored
                ],
                "total_pages": 1,
            },
        )
    )
    companies = await provider.search(CRITERIA, 10)

    params = route.calls.last.request.url.params
    assert params["activite_principale"] == "62.01Z,62.02A"
    assert params["tranche_effectif_salarie"] == "11,12"
    assert params["departement"] == "69"
    assert params["etat_administratif"] == "A"
    assert int(params["per_page"]) <= 25
    assert route.calls.last.request.headers["user-agent"].startswith("outreach-agents-bot/")

    assert len(companies) == 1
    officer = companies[0].officers[0]
    assert (officer.first_names, officer.last_name, officer.role) == (
        "Jeanne",
        "EXEMPLE",
        "Présidente",
    )
    assert not hasattr(officer, "annee_de_naissance")
    assert companies[0].website_domain is None  # never invented


@respx.mock
async def test_pagination_stops_at_the_limit(provider: RegistryCompanyProvider) -> None:
    sirens = ["104332184", "732829320", "552100554"]
    route = respx.get(f"{BASE_URL}/search").mock(
        side_effect=[
            httpx.Response(
                200, json={"results": [_result(s) for s in sirens[:2]], "total_pages": 5}
            ),
            httpx.Response(200, json={"results": [_result(sirens[2])], "total_pages": 5}),
        ]
    )
    companies = await provider.search(CRITERIA, 3)
    assert [c.siren for c in companies] == sirens
    assert route.call_count == 2


@respx.mock
async def test_rate_limit_is_retried_after_the_announced_delay(
    provider: RegistryCompanyProvider,
) -> None:
    route = respx.get(f"{BASE_URL}/search").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json={"results": [_result("104332184")], "total_pages": 1}),
        ]
    )
    assert len(await provider.search(CRITERIA, 5)) == 1
    assert route.call_count == 2


@respx.mock
async def test_server_errors_are_reported(provider: RegistryCompanyProvider) -> None:
    respx.get(f"{BASE_URL}/search").mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError, match="503"):
        await provider.search(CRITERIA, 5)
