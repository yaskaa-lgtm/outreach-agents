from __future__ import annotations

from app.providers.web.extract import extract_links, extract_text

HTML = b"""<!doctype html><html><head><title>Example</title></head><body>
<nav><a href="/tarifs">Tarifs</a> <a href="https://www.example.com/clients#top">Clients</a>
<a href="https://other.example.org/">Other site</a> <a href="/brochure.pdf">PDF</a>
<a href="mailto:contact@example.com">Mail</a> <a href="/tarifs">Tarifs again</a></nav>
<main><h1>Example SaaS</h1><p>Example SaaS aide les PME \xc3\xa0 envoyer leurs factures.</p>
<p>Plus de 400 clients nous font confiance depuis 2021.</p></main></body></html>"""


def test_extract_text_keeps_the_main_content() -> None:
    text = extract_text(HTML, "https://example.com/")
    assert "aide les PME à envoyer leurs factures" in text
    assert "Plus de 400 clients" in text


def test_extract_links_keeps_same_site_pages_only() -> None:
    links = extract_links(HTML, "https://example.com/")
    assert links == ["https://example.com/tarifs", "https://www.example.com/clients"]


def test_extract_handles_garbage() -> None:
    assert extract_links(b"", "https://example.com/") == []
    assert extract_text(b"", "https://example.com/") == ""
