"""The fictional website read in demo mode (no network access)."""

from __future__ import annotations

from typing import Self
from urllib.parse import urlsplit

from app.core.errors import FetchError
from app.providers.company.fake import DEMO_DOMAIN_PATTERN
from app.providers.web.fetcher import FetchedPage

DEMO_WEBSITE_URL = "https://nimbus-ledger.example.com/"

_HOME = """Nimbus Ledger — la facturation qui se relance toute seule
Nimbus Ledger est un logiciel de facturation en ligne pour les PME et les artisans.
Créez vos devis et factures en deux minutes, puis laissez Nimbus Ledger relancer
automatiquement les clients en retard de paiement.
Pensé pour les entreprises de 3 à 50 salariés qui n'ont pas de service comptable dédié.
Vos factures sont prêtes pour la facturation électronique obligatoire.
Tableau de bord de trésorerie : voyez en un coup d'œil qui vous doit combien."""

_PRICING = """Tarifs
Offre Essentiel : 29 € HT par mois, jusqu'à 50 factures par mois.
Offre Pro : 79 € HT par mois, factures illimitées et relances automatiques personnalisées.
Sans engagement, 14 jours d'essai gratuit."""

_CUSTOMERS = """Ils nous font confiance
Plus de 400 PME utilisent Nimbus Ledger au quotidien.
Menuiserie Exemple (Rhône) a réduit ses retards de paiement de 35 % en six mois.
Nos clients sont surtout des artisans du bâtiment, des cabinets de conseil et des agences."""

_ABOUT = """À propos
Nimbus Ledger a été fondée à Lyon en 2021.
Nous accompagnons les entreprises partout en France métropolitaine.
Notre support client répond en français, du lundi au vendredi."""

DEMO_PAGES: dict[str, str] = {
    DEMO_WEBSITE_URL: _HOME,
    DEMO_WEBSITE_URL + "tarifs": _PRICING,
    DEMO_WEBSITE_URL + "clients": _CUSTOMERS,
    DEMO_WEBSITE_URL + "a-propos": _ABOUT,
}


def _fake_company_page(url: str) -> FetchedPage | None:
    """Websites of the fictional prospects (`<name>-<siren>.example.com`, see
    app.providers.company.fake): a home page and a legal notice page showing the SIREN —
    except for one company in ten, whose legal notice omits it (domain stays unconfirmed)."""
    parts = urlsplit(url)
    match = DEMO_DOMAIN_PATTERN.match(parts.hostname or "")
    if match is None:
        return None
    siren = match.group(1)
    home = f"https://{parts.hostname}/"
    legal = f"{home}mentions-legales"
    if parts.path in ("", "/"):
        text = "Bienvenue sur le site de notre entreprise (site fictif de démonstration)."
        return FetchedPage(requested_url=url, url=home, text=text, links=[legal])
    if parts.path.rstrip("/") == "/mentions-legales":
        shown = "" if int(siren) % 10 == 3 else f"SIREN : {siren[:3]} {siren[3:6]} {siren[6:]}. "
        text = f"Mentions légales. Société fictive de démonstration. {shown}Hébergeur : exemple."
        return FetchedPage(requested_url=url, url=legal, text=text, links=[home])
    return None


class DemoWebFetcher:
    """Serves the fictional pages above; any other URL is refused."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def fetch_page(self, url: str) -> FetchedPage:
        fake_company = _fake_company_page(url)
        if fake_company is not None:
            return fake_company
        text = DEMO_PAGES.get(url) or DEMO_PAGES.get(url.rstrip("/") + "/")
        if text is None:
            raise FetchError("Demo mode: only the fictional demo websites can be read.", url=url)
        return FetchedPage(requested_url=url, url=url, text=text, links=list(DEMO_PAGES))
