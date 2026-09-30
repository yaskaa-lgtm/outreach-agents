# Reference data

Copied on 2026-09-30 from the `app/labels/` folder of
[annuaire-entreprises-data-gouv-fr/search-api](https://github.com/annuaire-entreprises-data-gouv-fr/search-api)
(the code behind `recherche-entreprises.api.gouv.fr`), MIT licence, last upstream change to
`codes-NAF.json` on 2024-08-16. Keys and labels are unchanged; files were renamed and
re-serialised with sorted keys.

| File | Upstream file | Content |
|---|---|---|
| `naf_codes.json` | `codes-NAF.json` | NAF rév. 2 sub-class codes → label (732 entries) |
| `departements.json` | `departements.json` | Département codes → name (109 entries) |
| `headcount_ranges.json` | `tranches-effectifs.json` | INSEE headcount range codes → label (16 entries) |

They are used to validate the segment criteria proposed by the ICP strategist (Agent 2),
so that every criterion can be sent as-is to the company search API in Phase 2.
