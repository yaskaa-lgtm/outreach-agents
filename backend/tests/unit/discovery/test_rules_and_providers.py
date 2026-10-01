"""Discovery building blocks without a database: rules, state machine, CSV, fake providers."""

from __future__ import annotations

import pytest

from app.compliance.email_rules import (
    email_hash,
    is_generic,
    is_valid_syntax,
    is_webmail,
    webmail_domains,
)
from app.demo.site import DemoWebFetcher
from app.discovery.domains import confirm_domain, contains_siren
from app.discovery.pipeline import rank_contact
from app.orchestrator.states import InvalidTransitionError, check_transition
from app.providers.company.base import is_valid_siren
from app.providers.company.csv_import import CsvImportError, normalize_domain, parse_companies_csv
from app.providers.company.fake import DEMO_DOMAIN_PATTERN, FakeCompanyProvider
from app.providers.contact.base import ContactCandidate
from app.providers.contact.fake import FakeContactFinder, FakeEmailVerifier
from app.schemas.segment import SegmentCriteria

CRITERIA = SegmentCriteria(
    naf_codes=["62.01Z"], headcount_ranges=["11", "12"], departements=[], keywords=[]
)


@pytest.mark.parametrize(
    ("email", "webmail", "generic", "valid"),
    [
        ("jane.doe@acme.example.com", False, False, True),
        ("Contact@ACME.example.com", False, True, True),
        ("someone@webmail.example", True, False, True),
        ("not-an-email", False, False, False),
    ],
)
def test_email_rules(email: str, webmail: bool, generic: bool, valid: bool) -> None:
    assert is_valid_syntax(email) is valid
    if valid:
        assert is_webmail(email) is webmail
        assert is_generic(email) is generic


def test_consumer_mailbox_domains_are_blocked() -> None:
    assert {"gmail.com", "orange.fr", "outlook.fr", "free.fr"} <= webmail_domains()


def test_email_hash_ignores_case_and_spaces() -> None:
    assert email_hash(" Jane@Example.COM ") == email_hash("jane@example.com")


def test_state_machine_rules() -> None:
    check_transition("discovered", "contact_found", None)
    with pytest.raises(InvalidTransitionError):
        check_transition("discovered", "sent", None)
    with pytest.raises(InvalidTransitionError, match="reason"):
        check_transition("contact_found", "excluded", None)


def test_siren_checksum_and_detection() -> None:
    assert is_valid_siren("104332184")
    assert not is_valid_siren("104332185")
    assert contains_siren("SIREN : 104 332 184 - RCS Lyon", "104332184")
    assert contains_siren("SIRET 104.332.184.00012", "104332184")
    assert not contains_siren("Tel 1104332184", "104332184")


def test_csv_import_with_aliases_and_errors() -> None:
    text = (
        "raison_sociale;siren;site_web;prenom;nom;email\n"
        "Acme Exemple;104332184;https://www.acme.example.org/contact;Jeanne;Exemple;j.exemple@acme.example.org\n"
        "Bad Siren;123456789;;;;\n"
        ";104332184;;;;\n"
    )
    result = parse_companies_csv(text)
    assert len(result.candidates) == 1
    company = result.candidates[0]
    assert company.website_domain == "acme.example.org"
    assert company.contacts[0].email == "j.exemple@acme.example.org"
    assert len(result.errors) == 2


def test_csv_import_needs_a_name_column() -> None:
    with pytest.raises(CsvImportError):
        parse_companies_csv("siren,website\n104332184,acme.example.org\n")


def test_normalize_domain() -> None:
    assert normalize_domain("HTTPS://WWW.Example.com/a?b") == "example.com"
    assert normalize_domain("not a domain") is None


async def test_fake_companies_are_deterministic_and_fictional() -> None:
    first = await FakeCompanyProvider().search(CRITERIA, 5)
    second = await FakeCompanyProvider().search(CRITERIA, 5)
    assert first == second
    for company in first:
        assert company.siren and is_valid_siren(company.siren)
        assert company.website_domain and DEMO_DOMAIN_PATTERN.match(company.website_domain)
        assert company.naf_code == "62.01Z"


async def test_demo_domain_confirmation_uses_the_legal_notice() -> None:
    fetcher = DemoWebFetcher()
    confirmed = await confirm_domain(fetcher, "104332184", "acme-104332184.example.com", 3)
    assert confirmed.status == "confirmed"
    assert confirmed.evidence_url == "https://acme-104332184.example.com/mentions-legales"
    # SIREN ending in 3: the fictional legal notice omits it on purpose.
    unconfirmed = await confirm_domain(fetcher, "100000033", "beta-100000033.example.com", 3)
    assert unconfirmed.status == "unconfirmed"
    missing = await confirm_domain(fetcher, "104332184", "unknown.example.net", 3)
    assert missing.status == "not_found"


async def test_fake_contacts_and_verification_are_deterministic() -> None:
    finder, verifier = FakeContactFinder(), FakeEmailVerifier()
    contacts = await finder.find("acme-104332184.example.com")
    assert contacts == await finder.find("acme-104332184.example.com")
    assert contacts[0].email
    assert await verifier.verify(contacts[0].email) == await verifier.verify(contacts[0].email)


def test_contact_ranking_prefers_matching_named_people_with_an_address() -> None:
    titles = ["Directeur administratif et financier"]
    officer = ContactCandidate("Jeanne", "Exemple", "Gérante", None, "registry")
    cfo = ContactCandidate(
        "Paul", "Exemple", "Directeur financier", "p.exemple@acme.example.org", "hunter"
    )
    generic = ContactCandidate(None, None, None, "contact@acme.example.org", "hunter")
    best = max([officer, generic, cfo], key=lambda c: rank_contact(c, titles))
    assert best is cfo
    # An officer whose title matches but who has no address cannot be emailed.
    manager = ContactCandidate("Jeanne", "Exemple", "Directeur financier", None, "registry")
    assert rank_contact(manager, titles)[1] > 0
    assert max([manager, generic], key=lambda c: rank_contact(c, titles)) is generic
