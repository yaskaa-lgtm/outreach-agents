# Learning log

What I learned at each phase, in my own words. One section per phase.

## Phase 0 — Foundations & security (2026-09-30)

**What was built**
- A Git repository whose `.gitignore` exists *before* the first commit, so `.env`, local data
  and CSV exports can never be committed by accident.
- A pre-commit setup: Git runs checks before accepting each commit (gitleaks for secrets,
  ruff for Python, file hygiene). A test proves that committing a fake key is refused.
- A backend skeleton (FastAPI `/health`, settings, logging that masks email addresses,
  an idle worker), a Next.js skeleton showing the active mode, and `docker compose up`
  starting database + API + worker + web + Mailpit.
- A CI pipeline on GitHub Actions: lint, types, tests, a full-history secret scan and a
  Docker smoke test on every push.

**Concepts**
- *Pre-commit hooks* — a security guard at the door of the repository: every commit is
  searched before it gets in, not after.
- *Environment variables and `.env`* — the code is the recipe, `.env` is the key to the
  pantry: the recipe can be published, the key stays at home.
- *Docker Compose* — one command that starts five small, isolated machines that talk to
  each other on a private network, identical on Windows and macOS.

**Surprises and fixes**
- Windows *Smart App Control* blocks unsigned `.exe` files, including the small launchers
  that Python tools create. Fix: run tools as `python -m <tool>` and run gitleaks in Docker.
- On Windows, `localhost` tries IPv6 first; Docker only listens on IPv4, so the database
  looked "down". Fix: use `127.0.0.1` in local defaults.
- psycopg's async mode needs a specific event loop on Windows (`SelectorEventLoop`).
- The first GitHub CI run failed although everything passed locally: `LayoutProps` is a type
  that Next.js generates into `.next/`, which existed on my machine but not on a fresh
  checkout. Fix: `next typegen` before `tsc`. Lesson: "works on my machine" is exactly what
  CI is for — and checks should be run from a clean clone before pushing.

**What I should be able to explain in an interview**
- Why secrets are blocked at three levels (local hook, CI scan of the full history, GitHub
  push protection) and why a leaked key must be revoked, not just deleted.
- Why the app starts in `DEMO` / `DRY_RUN` mode by default ("safe by default").
- What a health check is and how Docker Compose uses it to start services in order.
