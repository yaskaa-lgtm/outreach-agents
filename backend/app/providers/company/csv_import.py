"""Import of a company list supplied by the user (CSV text, comma or semicolon separated).

Recognised columns (case-insensitive, any order): siren, name (or company), website (or
domain), naf_code, postal_code, city, first_name, last_name, title, email. Only `name` is
required. Rows with an invalid SIREN or no name are reported, not imported.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.providers.company.base import CompanyCandidate, ProvidedContact, is_valid_siren

MAX_ROWS = 500
MAX_BYTES = 1_000_000

_ALIASES = {
    "company": "name",
    "company_name": "name",
    "raison_sociale": "name",
    "domain": "website",
    "site": "website",
    "site_web": "website",
    "naf": "naf_code",
    "code_naf": "naf_code",
    "code_postal": "postal_code",
    "ville": "city",
    "prenom": "first_name",
    "nom": "last_name",
    "poste": "title",
    "job_title": "title",
}


@dataclass(frozen=True)
class CsvImportResult:
    candidates: list[CompanyCandidate]
    errors: list[str]


class CsvImportError(ValueError):
    pass


def normalize_domain(value: str) -> str | None:
    """'https://www.Example.com/contact' -> 'example.com'; None if it is not a host name."""
    value = value.strip().lower()
    if not value:
        return None
    host = urlsplit(value if "://" in value else f"https://{value}").hostname or ""
    host = host.removeprefix("www.")
    return host if "." in host and " " not in host else None


def parse_companies_csv(text: str) -> CsvImportResult:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise CsvImportError("The file is larger than 1 MB.")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise CsvImportError("The file has no header line.")
    columns = {
        name: _ALIASES.get(name.strip().lower(), name.strip().lower()) for name in reader.fieldnames
    }
    if "name" not in columns.values():
        raise CsvImportError("A 'name' column is required.")

    candidates: list[CompanyCandidate] = []
    errors: list[str] = []
    for line_number, raw in enumerate(reader, start=2):
        if len(candidates) >= MAX_ROWS:
            errors.append(f"Only the first {MAX_ROWS} rows were imported.")
            break
        row = {columns[key]: (value or "").strip() for key, value in raw.items() if key in columns}
        name = row.get("name", "")
        siren = row.get("siren", "").replace(" ", "")
        if not name:
            errors.append(f"Line {line_number}: missing name.")
            continue
        if siren and not is_valid_siren(siren):
            errors.append(f"Line {line_number}: invalid SIREN.")
            continue
        contact = ProvidedContact(
            first_name=row.get("first_name") or None,
            last_name=row.get("last_name") or None,
            title=row.get("title") or None,
            email=row.get("email") or None,
        )
        has_contact = any([contact.first_name, contact.last_name, contact.email])
        candidates.append(
            CompanyCandidate(
                name=name,
                source="csv",
                siren=siren or None,
                naf_code=row.get("naf_code") or None,
                postal_code=row.get("postal_code") or None,
                city=row.get("city") or None,
                website_domain=normalize_domain(row.get("website", "")),
                contacts=[contact] if has_contact else [],
            )
        )
    return CsvImportResult(candidates=candidates, errors=errors)
