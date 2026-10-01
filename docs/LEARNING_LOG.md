# Learning log

What I learned at each phase, in my own words. One section per phase.

## Phase 2 — Discovery: companies, contacts, job queue (2026-10-01)

**What was built**
- A job queue inside PostgreSQL and a worker that runs it: launching a campaign queues one
  search per segment, each company found queues its own processing job.
- Company sources behind one interface: the official French registry, a CSV import, and a
  fake provider for demo mode and tests.
- Domain confirmation by SIREN, contact selection, address verification and a prospect state
  machine where every change is recorded with its reason.
- Screen 3: launch, live progress, filters, prospect detail with the proof.

**Concepts**
- *Job queue with `SKIP LOCKED`* — each worker takes the first job nobody holds and skips the
  locked ones instead of waiting. Like cashiers taking the next customer in line: two
  cashiers never serve the same customer, and nobody waits for a busy cashier.
- *Idempotency* — running the same job twice gives the same result as once (unique keys, state
  checks). Like pressing a lift button twice: it does not call two lifts.
- *Exponential backoff* — after each failure, wait twice as long before retrying (plus a bit of
  randomness), then give up (`dead`). Like calling back someone who does not answer.
- *Proof before trust* — a domain is accepted only when the company's SIREN is on its site,
  an address only when it is on that domain and verified. Each rule lives in code, not in a
  prompt.

**Surprises and fixes**
- The Docker image shipped stale code: uv reuses a cached build of a local package until its
  `pyproject.toml` changes. Found because the worker logged an old message.
- `faker` was a test dependency but demo mode needs it at runtime: the API crashed in Docker
  while every local test passed. Lesson: always try the real stack, not only the tests.
- In the demo, an officer with the right title but no address was chosen over a reachable
  `contact@` address: the ranking now puts "has an address" first.

**What I should be able to explain in an interview**
- Why the discovery agents use no LLM (rules are cheaper, reproducible and testable).
- How the queue survives crashes, retries and the LLM budget pause.
- Which checks an address must pass before it can ever be sent to, and why.

## Phase 1 — Data model, LLM layer, offer analysis and segments (2026-09-30)

**What was built**
- A database schema managed by Alembic migrations, a single admin login with server-side
  sessions, and an audit log of every important action.
- An `LLMClient` interface with two implementations: the real Anthropic API and a fake,
  deterministic LLM that replays recorded answers (tests and demo mode need no API key).
- A safe web reader (SSRF protection, robots.txt, size/time limits) and two agents: one that
  describes what the client sells with a source for every claim, one that proposes customer
  segments with criteria checked against official French lists.
- Cost tracking in euros with a daily budget, and two web screens using a typed API client
  generated from the OpenAPI schema.

**Concepts**
- *Structured outputs* — instead of asking the model "please answer in JSON", the API is given
  the exact JSON schema to follow, then Pydantic checks the answer (with one retry if not).
  Like a form with fixed fields instead of a blank page.
- *SSRF* — tricking a server into fetching an internal address (a database, a cloud metadata
  service) on the attacker's behalf. Like asking the receptionist to fetch "the red folder in
  the manager's office": the building must decide which rooms visitors may send someone to.
- *Evidence check* — the model must quote the sentence it relied on, and code verifies that
  the sentence really is on the page. Trust, but verify — with a program, not with the model.

**Surprises and fixes**
- Windows Smart App Control also blocks some compiled Python extensions (`charset_normalizer`):
  the pure-Python version of that package is installed instead.
- With async SQLAlchemy, values computed by PostgreSQL (timestamps) must be returned at write
  time (`eager_defaults`), otherwise reading them later fails.

**What I should be able to explain in an interview**
- Why an orchestrated pipeline of narrow agents instead of one free agent (ADR 0001).
- How hallucinations are limited: sourced claims, exact-excerpt check in code, schemas.
- How prompt injection is limited: untrusted-content tags, no action tools, code-side checks.
- How LLM costs are measured and capped.

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
