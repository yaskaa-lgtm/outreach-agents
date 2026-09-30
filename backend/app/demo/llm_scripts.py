"""Recorded answers of the fake LLM in demo mode.

Every excerpt below is copied from the fictional pages in `app.demo.site`, so the
anti-hallucination check keeps the claims exactly as it would with a real model.
"""

from __future__ import annotations

from app.agents.icp_strategist import AGENT_NAME as ICP_STRATEGIST
from app.agents.offer_analyst import AGENT_NAME as OFFER_ANALYST
from app.demo.site import DEMO_WEBSITE_URL
from app.providers.llm.fake import FakeLLM, Script, final_answer, tool_use
from app.schemas.offer import OfferProfileData, SourcedClaim
from app.schemas.segment import SegmentCriteria, SegmentProposal, SegmentStrategy

HOME = DEMO_WEBSITE_URL
PRICING = DEMO_WEBSITE_URL + "tarifs"
CUSTOMERS = DEMO_WEBSITE_URL + "clients"
ABOUT = DEMO_WEBSITE_URL + "a-propos"


def _claim(claim: str, url: str, excerpt: str) -> SourcedClaim:
    return SourcedClaim(claim=claim, source_url=url, excerpt=excerpt)


DEMO_OFFER_PROFILE = OfferProfileData(
    company_name="Nimbus Ledger",
    summary=(
        "Nimbus Ledger édite un logiciel de facturation en ligne qui relance automatiquement "
        "les clients en retard de paiement. Il s'adresse aux PME de 3 à 50 salariés et aux "
        "artisans sans service comptable dédié."
    ),
    offerings=[
        _claim(
            "Logiciel de facturation en ligne (devis et factures).",
            HOME,
            "Nimbus Ledger est un logiciel de facturation en ligne pour les PME et les artisans.",
        ),
        _claim(
            "Relances automatiques des clients en retard de paiement.",
            HOME,
            "laissez Nimbus Ledger relancer automatiquement les clients en retard de paiement",
        ),
        _claim(
            "Tableau de bord de trésorerie.",
            HOME,
            "Tableau de bord de trésorerie : voyez en un coup d'œil qui vous doit combien.",
        ),
    ],
    target_customers=[
        _claim(
            "PME de 3 à 50 salariés sans service comptable dédié.",
            HOME,
            "Pensé pour les entreprises de 3 à 50 salariés qui n'ont pas de service comptable dédié.",
        ),
        _claim(
            "Artisans du bâtiment, cabinets de conseil et agences.",
            CUSTOMERS,
            "Nos clients sont surtout des artisans du bâtiment, des cabinets de conseil et des agences.",
        ),
    ],
    value_proposition=_claim(
        "Des factures créées vite et des relances automatiques pour être payé à temps.",
        HOME,
        "Créez vos devis et factures en deux minutes",
    ),
    differentiators=[
        _claim(
            "Prêt pour la facturation électronique obligatoire.",
            HOME,
            "Vos factures sont prêtes pour la facturation électronique obligatoire.",
        ),
    ],
    pricing=[
        _claim(
            "Offre Essentiel à 29 € HT par mois.", PRICING, "Offre Essentiel : 29 € HT par mois"
        ),
        _claim("Offre Pro à 79 € HT par mois.", PRICING, "Offre Pro : 79 € HT par mois"),
    ],
    geography=[
        _claim(
            "Clients dans toute la France métropolitaine.",
            ABOUT,
            "Nous accompagnons les entreprises partout en France métropolitaine.",
        ),
    ],
    proof_points=[
        _claim(
            "Plus de 400 PME clientes.",
            CUSTOMERS,
            "Plus de 400 PME utilisent Nimbus Ledger au quotidien.",
        ),
        _claim(
            "Un client a réduit ses retards de paiement de 35 % en six mois.",
            CUSTOMERS,
            "a réduit ses retards de paiement de 35 % en six mois",
        ),
    ],
    competitors_mentioned=[],
    missing_information=["Aucun concurrent n'est mentionné sur le site."],
)

DEMO_SEGMENTS = SegmentStrategy(
    segments=[
        SegmentProposal(
            name="Artisans et petites entreprises du bâtiment",
            description="Menuisiers, électriciens et plombiers qui facturent chantier par chantier.",
            criteria=SegmentCriteria(
                naf_codes=["43.32A", "43.21A", "43.22A"],
                headcount_ranges=["02", "03", "11", "12"],
                departements=[],
                keywords=["artisan", "chantier"],
            ),
            target_titles=["Gérant", "Dirigeant", "Responsable administratif"],
            main_pain="Les retards de paiement pèsent sur la trésorerie entre deux chantiers.",
            hook_angle="Un client artisan a réduit ses retards de paiement de 35 % en six mois.",
            fit_score=86,
            fit_rationale=(
                "Le site cite explicitement les artisans du bâtiment parmi ses clients et un "
                "résultat chiffré obtenu par une menuiserie."
            ),
        ),
        SegmentProposal(
            name="Cabinets de conseil aux entreprises",
            description="Petits cabinets de conseil qui facturent des missions au forfait ou au temps passé.",
            criteria=SegmentCriteria(
                naf_codes=["70.22Z", "62.02A"],
                headcount_ranges=["02", "03", "11", "12"],
                departements=[],
                keywords=["conseil", "cabinet"],
            ),
            target_titles=["Associé gérant", "Directeur administratif et financier"],
            main_pain="Le temps passé à relancer les clients au lieu de produire des missions facturables.",
            hook_angle="Des relances automatiques qui partent sans y penser, en restant courtoises.",
            fit_score=72,
            fit_rationale=(
                "Les cabinets de conseil sont cités parmi les clients, mais le site ne donne "
                "pas de résultat chiffré pour ce segment."
            ),
        ),
        SegmentProposal(
            name="Agences de communication",
            description="Agences de publicité et de relations publiques de taille petite ou moyenne.",
            criteria=SegmentCriteria(
                naf_codes=["73.11Z", "70.21Z"],
                headcount_ranges=["03", "11", "12"],
                departements=[],
                keywords=["agence", "communication"],
            ),
            target_titles=["Directeur général", "Responsable administratif et financier"],
            main_pain="Des factures d'acompte et de solde nombreuses, difficiles à suivre.",
            hook_angle="Un tableau de bord qui montre en un coup d'œil qui doit combien.",
            fit_score=61,
            fit_rationale=(
                "Les agences sont mentionnées comme clientes, sans preuve spécifique : "
                "adéquation plausible mais moins étayée."
            ),
        ),
    ]
)


def build_demo_llm() -> FakeLLM:
    return FakeLLM(
        {
            OFFER_ANALYST: Script(
                [
                    tool_use("fetch_page", {"url": HOME}, "toolu_demo_1"),
                    tool_use("fetch_page", {"url": PRICING}, "toolu_demo_2"),
                    tool_use("fetch_page", {"url": CUSTOMERS}, "toolu_demo_3"),
                    tool_use("fetch_page", {"url": ABOUT}, "toolu_demo_4"),
                    final_answer(DEMO_OFFER_PROFILE),
                ]
            ),
            ICP_STRATEGIST: Script([final_answer(DEMO_SEGMENTS)]),
        }
    )
