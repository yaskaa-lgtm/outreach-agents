# Decision log

Short records of technical decisions: date, decision, alternatives, reason.
Bigger architectural choices get a full ADR in [`adr/`](adr/).

| Date | Decision | Alternatives | Reason |
|---|---|---|---|
| 2026-09-30 | Orchestrated pipeline (deterministic state machine + specialised agents) | One autonomous "free" agent | Reliable, testable, debuggable. See [ADR 0001](adr/0001-orchestrated-pipeline.md). |
| 2026-09-30 | uv **workspace** at the repo root, backend as a member package (`backend/app`) | Standalone `backend/` project | One `.venv` and one lockfile; `uv run python -m evals.run` works from the root as required. |
| 2026-09-30 | psycopg 3 as the only PostgreSQL driver | asyncpg (app) + psycopg2 (Alembic) | One dependency for async and sync code; binary wheels on Windows and macOS. |
| 2026-09-30 | Python 3.12 | 3.13 / 3.14 | Minimum required by the brief, widest library support. Can move up later. |
| 2026-09-30 | PostgreSQL 18 (`postgres:18-alpine`), volume on `/var/lib/postgresql` | PostgreSQL 17 | Current stable major; the 18+ image expects that volume path ([Docker Hub](https://hub.docker.com/_/postgres)). |
| 2026-09-30 | npm for the web app | pnpm | Ships with Node.js: nothing extra to install on either machine or for a recruiter. |
| 2026-09-30 | Next.js standalone build in Docker; server components call the API over the compose network | `next dev` inside Docker | Production-like `docker compose up`; bind-mount file watching is slow on Windows. Day-to-day development runs `npm run dev` locally. |
| 2026-09-30 | gitleaks pre-commit hook runs the **official Docker image** (`ghcr.io/gitleaks/gitleaks:v8.30.1`) | Upstream `gitleaks` hook (`language: golang`) | On the Windows machine, *Smart App Control* blocked the Go toolchain downloaded by pre-commit (`WinError 4551`). Docker behaves identically on Windows and macOS and is already required. Trade-off: Docker must be running to commit. |
| 2026-09-30 | All other pre-commit hooks are `repo: local` hooks run as `python -m <module>` | Upstream hook repos | Same Smart App Control issue: the `.exe` launchers pre-commit generates are blocked, `python.exe` is not. Versions pinned via `additional_dependencies`. |
| 2026-09-30 | Documented commands use `uv run python -m <tool>` | `uv run <tool>` | Same reason: `.venv\Scripts\<tool>.exe` launchers are blocked by Smart App Control; `python -m` works everywhere. |
| 2026-09-30 | Local API on Windows must run with `uvicorn --reload` | Plain `uvicorn` | psycopg's async mode cannot use Windows' default `ProactorEventLoop` ([psycopg docs](https://www.psycopg.org/psycopg3/docs/advanced/async.html)); uvicorn selects a `SelectorEventLoop` when `--reload` is on. The worker and the tests set the selector loop explicitly. Docker (Linux) is not affected. |
| 2026-09-30 | Local defaults use `127.0.0.1`, not `localhost` | `localhost` | On Windows `localhost` tries IPv6 first; Docker publishes ports on IPv4 only, and the refused IPv6 attempt made the database connection time out. |
| 2026-09-30 | `httpx2` as a **test-only** dependency | Ignore the warning | Starlette 1.7's `TestClient` deprecates `httpx` in favour of `httpx2` (maintained by the Pydantic team). Production code keeps `httpx` as specified in the brief; to be re-evaluated in Phase 1 (`TODO(verify)`). |
| 2026-09-30 | CI secret scan runs the pinned gitleaks Docker image on the full history | `gitleaks/gitleaks-action` | Same version and config as the local hook; always scans the whole history (the action scans only the pushed commits on `push` events). |
| 2026-09-30 | GitHub Actions pinned to commit SHAs (version in a comment) | Major version tags (`@v7`) | Supply-chain safety: a tag can be moved, a SHA cannot. |
| 2026-09-30 | Commits authored with the GitHub `noreply` address (repo-local Git config) | Global Git identity | The global identity contains a real email address; the brief forbids real emails in commits. |
| 2026-09-30 | English for every repository document except `README.fr.md`; French in chat | French docs | The public repository targets recruiters. |
| 2026-09-30 | Default LLM models: `claude-sonnet-5-5` (reasoning/writing), `claude-haiku-4-5` (fast classification), set in `.env` | Hard-coded names | Verified on the [models overview](https://platform.claude.com/docs/en/about-claude/models/overview). Haiku 4.5 retires "not sooner than October 15, 2026": switching is a `.env` change. |
