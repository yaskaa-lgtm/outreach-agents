"""Official French company registry: https://recherche-entreprises.api.gouv.fr (free, no key).

Checked on its OpenAPI description (https://recherche-entreprises.api.gouv.fr/openapi.json)
on 2026-10-01:
- `GET /search`; filters `activite_principale`, `tranche_effectif_salarie` and `departement`
  accept a single value or a comma-separated list; `etat_administratif=A` keeps active
  companies; `per_page` is limited to 25.
- At most 7 requests per second per IP; HTTP 429 with a `Retry-After` header when exceeded;
  an explicit User-Agent is recommended.
- Officers (`dirigeants`) of type "personne physique" have `nom`, `prenoms`, `qualite`;
  only those three fields are kept (data minimisation: no birth date, no nationality).
- The registry has no website field: domains come from elsewhere and are confirmed by SIREN.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import FetchError
from app.providers.company.base import CompanyCandidate, Officer, is_valid_siren
from app.schemas.segment import SegmentCriteria

BASE_URL = "https://recherche-entreprises.api.gouv.fr"
MAX_PER_PAGE = 25
MAX_RETRIES = 3


class RegistryCompanyProvider:
    name = "registry"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval = settings.registry_min_interval_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_call: float | None = None
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            transport=transport,
            timeout=httpx.Timeout(20.0, connect=5.0),
            headers={"User-Agent": settings.bot_user_agent, "Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search(self, criteria: SegmentCriteria, limit: int) -> list[CompanyCandidate]:
        params: dict[str, Any] = {
            "activite_principale": ",".join(criteria.naf_codes),
            "tranche_effectif_salarie": ",".join(criteria.headcount_ranges),
            "etat_administratif": "A",
            "per_page": min(MAX_PER_PAGE, limit),
        }
        if criteria.departements:
            params["departement"] = ",".join(criteria.departements)

        candidates: list[CompanyCandidate] = []
        page = 1
        while len(candidates) < limit:
            body = await self._get({**params, "page": page})
            for result in body.get("results", []):
                candidate = _to_candidate(result)
                if candidate is not None:
                    candidates.append(candidate)
                if len(candidates) >= limit:
                    break
            if page >= int(body.get("total_pages") or 0):
                break
            page += 1
        return candidates

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(MAX_RETRIES + 1):
            await self._throttle()
            try:
                response = await self._client.get("/search", params=params)
            except httpx.HTTPError as exc:
                raise FetchError(f"Company registry unreachable ({type(exc).__name__}).") from exc
            if response.status_code == 429 and attempt < MAX_RETRIES:
                await self._sleep(_retry_after(response, attempt))
                continue
            if response.status_code >= 400:
                raise FetchError(f"Company registry answered HTTP {response.status_code}.")
            data: dict[str, Any] = response.json()
            return data
        raise FetchError("Company registry rate limit: try again later.")

    async def _throttle(self) -> None:
        if self._last_call is not None:
            delay = self._min_interval - (self._clock() - self._last_call)
            if delay > 0:
                await self._sleep(delay)
        self._last_call = self._clock()


def _retry_after(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("retry-after", "")
    if header.isdigit():
        return float(min(int(header), 60))
    return float(2**attempt)


def _to_candidate(result: dict[str, Any]) -> CompanyCandidate | None:
    siren = str(result.get("siren") or "")
    if not is_valid_siren(siren):
        return None
    siege = result.get("siege") or {}
    complements = result.get("complements") or {}
    officers = [
        Officer(
            first_names=str(officer.get("prenoms") or "").strip(),
            last_name=str(officer.get("nom") or "").strip(),
            role=(str(officer["qualite"]).strip() or None) if officer.get("qualite") else None,
        )
        for officer in result.get("dirigeants") or []
        if officer.get("type_dirigeant") == "personne physique" and officer.get("nom")
    ]
    return CompanyCandidate(
        name=str(result.get("nom_complet") or result.get("nom_raison_sociale") or siren),
        source="registry",
        siren=siren,
        naf_code=result.get("activite_principale"),
        headcount_range=result.get("tranche_effectif_salarie"),
        postal_code=siege.get("code_postal"),
        city=siege.get("libelle_commune"),
        departement=siege.get("departement"),
        is_sole_trader=bool(complements.get("est_entrepreneur_individuel")),
        officers=officers,
    )
