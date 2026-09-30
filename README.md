# outreach-agents

AI agents that research B2B prospects and draft **sourced, compliant** cold emails — with a
human approving every email before it leaves.

> **Status: work in progress — Phase 0 (foundations & security) done.**
> No prospecting feature exists yet. This README only describes what works today; the full
> roadmap is in [docs/PLAN.md](docs/PLAN.md).

## What works today

- `docker compose up` starts the whole stack: PostgreSQL, a FastAPI API, a background worker
  (idle for now), a Next.js web app and Mailpit (a local SMTP server that captures emails).
- The web app shows a permanent banner with the active mode (`DEMO` / `DRY RUN` / `LIVE`) and
  the health of the API and database.
- Safe defaults: `DEMO_MODE=true`, `DRY_RUN=true`, every port bound to `127.0.0.1`.
- Secret protection: `.gitignore` written before the first commit, a gitleaks pre-commit hook
  (with an automated test proving a fake secret is blocked) and a full-history gitleaks scan
  in CI.

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

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · psycopg 3 · PostgreSQL 18 · uv ·
Next.js 16 (App Router) · TypeScript · Tailwind CSS · shadcn/ui · Docker Compose ·
GitHub Actions · gitleaks · pre-commit.

## Documentation

- [Implementation plan and roadmap](docs/PLAN.md)
- [Security policy](docs/SECURITY.md)
- [Technical decisions](docs/DECISIONS.md) and [ADRs](docs/adr/)
- [GitHub repository setup](docs/GITHUB_SETUP.md)
- [Learning log](docs/LEARNING_LOG.md)

## License

[MIT](LICENSE)
