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
| 2026-09-30 | Default LLM models: `claude-sonnet-5-5` (reasoning/writing), `claude-haiku-4-5` (fast classification), set in `.env` | Hard-coded names | Verified on the [models overview](https://platform.claude.com/docs/en/about-claude/models/overview). Haiku 4.5 is **Active**, tentative retirement "not sooner than October 15, 2026" ([model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)); switching is a `.env` change. |
| 2026-09-30 | Single admin account: `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env` at first start, argon2 hash, `HttpOnly` + `Secure` + `SameSite=Lax` session cookie, rate-limited login, demo account in `DEMO_MODE` | No authentication (localhost only) | Validated by the developer. The data model stays multi-tenant. |
| 2026-09-30 | Daily LLM budget in euros (default 2 €, `USD_TO_EUR_RATE` in `.env`): warning at 80 %, LLM work paused (not failed) at 100 % | Hard stop with errors | Validated by the developer. An Anthropic Console spend limit is the second safety net. |
| 2026-09-30 | IMAP through the standard-library `imaplib` in `asyncio.to_thread`, behind an `InboxReader` interface | `aioimaplib` | `aioimaplib` is GPL-3.0; the project is MIT and meant to become a SaaS. |
| 2026-09-30 | One branch + one pull request per phase from Phase 1; merge only with green CI, by the developer | Commit to `main` | Reviewable history, CI as a gate. |
| 2026-09-30 | The French brief is kept as `docs/PROJECT_BRIEF.fr.md` | Translate it | It is the developer's original specification. |
| 2026-09-30 | `npm run typecheck` runs `next typegen` before `tsc` | Commit generated types | `LayoutProps` and route types are generated into `.next/` (git-ignored). The first CI run failed because they were missing on a fresh checkout. |

## Dependencies and licences

Rule: the licence of every new dependency is checked before it is added and listed here.
Strong copyleft licences (GPL, AGPL) are refused; weak copyleft (LGPL, MPL) is accepted only
when used unmodified as a library, and is listed with a note.

### Backend (Python) — runtime

| Package | Version | Licence | Note |
|---|---|---|---|
| fastapi | 0.142.1 | MIT | |
| uvicorn | 0.54.0 | BSD-3-Clause | |
| pydantic | 2.13.5 | MIT | |
| pydantic-settings | 2.15.0 | MIT | |
| sqlalchemy | 2.1.1 | MIT | |
| psycopg / psycopg-binary | 3.3.6 | **LGPL-3.0-only** | Weak copyleft: imported unmodified as a library, which the LGPL allows from MIT or proprietary code; the licence notice must ship with any distributed image. Apache-2.0 alternative if ever needed: `asyncpg` (plus Alembic's async template). |
| httpx | 0.28.1 | BSD-3-Clause | |

### Backend (Python) — development only

| Package | Version | Licence |
|---|---|---|
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| pytest-cov | 7.1.0 | MIT |
| ruff | 0.16.9 | MIT |
| mypy | 2.3.1 | MIT |
| pre-commit | 4.6.2 | MIT |
| httpx2 | 2.13.1 | BSD-3-Clause |

### Web (npm)

| Package | Version | Licence |
|---|---|---|
| next | 16.3.7 | MIT |
| react / react-dom | 19.2.8 | MIT |
| @base-ui/react | 1.8.0 | MIT |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| cn | 0.4.0 | MIT |
| lucide-react | 1.49.0 | ISC |
| shadcn | 4.21.0 | MIT |
| tw-animate-css | 1.4.0 | MIT |
| tailwindcss / @tailwindcss/postcss | 4.3.3 | MIT |
| typescript (dev) | 5.9.3 | Apache-2.0 |
| eslint / eslint-config-next (dev) | 9.39.5 / 16.3.7 | MIT |
| prettier / prettier-plugin-tailwindcss (dev) | 3.9.9 / 0.8.1 | MIT |
| @types/node, @types/react, @types/react-dom (dev) | 20.x / 19.x | MIT |

### Tools run in Docker or CI (not bundled)

| Tool | Version | Licence |
|---|---|---|
| gitleaks (image `ghcr.io/gitleaks/gitleaks`) | 8.30.1 | MIT |
| Mailpit (image `axllent/mailpit`) | 1.31.3 | MIT |
| PostgreSQL (image `postgres`) | 18 | PostgreSQL Licence |
| pre-commit-hooks | 6.0.0 | MIT |
