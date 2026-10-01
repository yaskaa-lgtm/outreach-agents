# outreach-agents

AI agents that research B2B prospects and draft **sourced, compliant** cold emails — with a
human approving every email before it leaves.

> **Status: work in progress — Phases 0 (foundations), 1 (offer analysis and segments) and
> 2 (company and contact discovery) done.** No email is written or sent yet. This README only describes what works today; the full
> roadmap is in [docs/PLAN.md](docs/PLAN.md).

## What works today

- **Screen 1 — "What do you sell?"**: an agent reads the client's own website (a few pages,
  robots.txt respected) and writes an offer profile. Every claim carries the exact sentence
  and the page it comes from; claims whose sentence is not really on the page are removed in
  code before anyone sees them. The user reviews, edits and validates the profile.
- **Screen 2 — "Who needs it?"**: a second agent proposes 3 to 6 customer segments with
  search criteria checked against official French lists (NAF codes, headcount ranges,
  départements), the decision makers to contact, a fit score and its justification.
- **Screen 3 — Campaigns**: launch a search on the selected segments. A background worker
  finds companies in the official French registry (or a CSV you import), confirms each
  company's website by finding its SIREN on the legal notice page, picks a decision maker and
  checks the address. Only a `valid` address on the confirmed domain is marked sendable;
  personal webmail addresses are excluded. Every step is visible per prospect, with its proof.
- **Cost control**: every LLM call is journaled with its cost in euros; a daily budget
  warns at 80 % and pauses LLM work at 100 %.
- **Security**: login with a single admin account, SSRF-safe web reading, prompt-injection
  defences (web content is data, never instructions), strict Content-Security-Policy,
  rate limiting, secret scanning before every commit and on the whole Git history in CI.
- **Demo mode (default)**: no API key needed. A deterministic fake LLM analyses a fictional
  company (`nimbus-ledger.example.com`), and discovery uses fictional companies and contacts
  (Faker, `example.com` sites with their own legal notice pages). Log in with `demo@example.com` / `demo-password`
  (fake, public credentials that only work in demo mode).
- `docker compose up` starts everything: PostgreSQL (migrated automatically), the FastAPI
  API, the background worker (PostgreSQL job queue), the Next.js web app and Mailpit.

## Quick start

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows or
macOS). No API key needed.

```bash
git clone https://github.com/yaskaa-lgtm/outreach-agents.git
cd outreach-agents
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Mailpit inbox | http://localhost:8025 |

Stop with `Ctrl+C`, then `docker compose down` (add `-v` to also delete the database).

## Development

Requirements: [uv](https://docs.astral.sh/uv/), Node.js 24, Docker Desktop.
Commands are identical on Windows (PowerShell) and macOS (Terminal).

```bash
uv sync                                   # Python environment (.venv) for backend + evals
uv run python -m pre_commit install       # Git hooks: gitleaks, ruff, hygiene checks
docker compose up -d db mailpit           # only the database and Mailpit
uv run python -m alembic -c backend/alembic.ini upgrade head               # database schema

uv run python -m uvicorn app.main:app --reload --reload-dir backend/app   # API on :8000
uv run python -m app.worker                                               # worker

cd web && npm install && npm run dev      # web app on :3000
```

Quality checks (the same ones run in CI):

```bash
uv run python -m pytest                   # backend tests
uv run python -m ruff check . && uv run python -m ruff format --check .
uv run python -m mypy                     # type checking
uv run python -m pre_commit run --all-files
cd web && npm run lint && npm run typecheck && npm run format:check && npm run build
```

`python -m …` is used on purpose: on Windows with *Smart App Control* enabled, the small
`.exe` launchers generated in `.venv\Scripts` are blocked, while `python.exe` is trusted.

## Tech stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 + Alembic · psycopg 3 · PostgreSQL 18 ·
Anthropic API (structured outputs, tool use) · trafilatura · uv · Next.js 16 (App Router,
server actions) · TypeScript · Tailwind CSS · shadcn/ui · OpenAPI-generated client ·
Docker Compose · GitHub Actions · gitleaks · pre-commit.

To use the real LLM: set `DEMO_MODE=false`, `ANTHROPIC_API_KEY`, `ADMIN_EMAIL` and
`ADMIN_PASSWORD` in `.env` (see `.env.example`), keep `DRY_RUN=true`, and set a spend limit in
the Anthropic Console as well. Real company search needs no key (official registry); without
a `HUNTER_API_KEY`, contacts are the registry's company officers without an email address,
so nothing becomes sendable.

## Documentation

- [Implementation plan and roadmap](docs/PLAN.md)
- [Security policy](docs/SECURITY.md)
- [Technical decisions](docs/DECISIONS.md) and [ADRs](docs/adr/)
- [GitHub repository setup](docs/GITHUB_SETUP.md)
- [Learning log](docs/LEARNING_LOG.md)

## License

[MIT](LICENSE)
