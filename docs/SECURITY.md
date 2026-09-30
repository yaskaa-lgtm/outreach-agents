# Security policy

This repository is **public**. Anything committed, even for a minute, must be considered
published forever (forks, caches, the Git history).

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") on this repository.

## Secrets

| Rule | How it is enforced |
|---|---|
| Secrets only live in `.env`, which is never committed | `.gitignore` (written before the first commit), a `forbid-env-files` pre-commit hook, a test that fails if a `.env*` file (other than `.env.example`) is tracked |
| `.env.example` contains fake placeholders only | Test `test_env_example_contains_only_placeholder_secrets` |
| No secret can be committed | gitleaks pre-commit hook (official Docker image, pinned version) + automated test proving that a commit with a fake key is blocked |
| No secret exists anywhere in the history | CI job scanning the **full** Git history with gitleaks on every push and pull request |
| GitHub-side safety net | Secret Protection + Push protection enabled on the repository (see [GITHUB_SETUP.md](GITHUB_SETUP.md)) |
| Secrets never appear in logs or error messages | `SecretStr` settings (hidden in `repr`), database errors logged by type only |

### If a secret is committed by mistake

1. **Revoke the key immediately** at the provider (Anthropic console, Hunter dashboard, …).
   Deleting it in a new commit is *not* enough: it remains in the Git history.
2. Create a new key and put it in `.env` only.
3. Only then, clean the history if needed (for example with `git filter-repo`) — revocation
   comes first because the old key must be assumed compromised.

## Personal data

- Test and demo data are generated with Faker on reserved domains (`example.com`,
  `example.org`, `.test`). No real person ever appears in the repository.
- Git commits use the GitHub `noreply` address, not a personal email address.
- Logs mask email addresses (`jane.doe@example.com` → `j***@example.com`) and never contain
  full email bodies.
- From Phase 1: SMTP/IMAP credentials stored in the database are encrypted at rest with
  Fernet (`FERNET_KEY` in `.env`).

## Local development defaults

- Every Docker port is bound to `127.0.0.1`: nothing is reachable from the local network.
- The PostgreSQL password in `.env.example` / `docker-compose.yml` (`outreach_dev_password`)
  is a **local development default**, not a secret. Change it for any other deployment.
- Containers run as non-root users (`appuser` for the backend, `node` for the web app).
- The API only accepts cross-origin requests from the configured web origins (CORS
  allow-list). The web app sends baseline security headers (`X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`).

## Authentication (Phase 1)

- One admin account, created at first start from `ADMIN_EMAIL` / `ADMIN_PASSWORD` (`.env`,
  at least 12 characters). Passwords are hashed with argon2id; unknown emails spend the same
  hashing time, so response time does not reveal which accounts exist.
- Sessions are server-side: the cookie holds a random 256-bit token (`HttpOnly`, `Secure`,
  `SameSite=Lax`), the database stores only its SHA-256 hash. Logout revokes it at once.
- After 5 failed logins an address is locked for 15 minutes (a looser limit also applies per
  client address). These counters live in memory (single-process MVP).
- The demo account (`demo@example.com`, public password) only works while `DEMO_MODE=true`:
  it is refused at login and its sessions are rejected as soon as demo mode is off.
- The browser never calls the API directly: Next.js server components and server actions do,
  forwarding the session cookie (backend-for-frontend).

## Reading the web safely (Phase 1)

Every page an agent reads goes through `SafeWebFetcher`
([`backend/app/providers/web/fetcher.py`](../backend/app/providers/web/fetcher.py)):

- **SSRF**: only `http(s)` on the default ports, no credentials in URLs, no local host names;
  the host name must resolve only to public addresses, and the address actually connected to
  is checked again (against DNS rebinding); every redirect (max 3) goes through the same checks;
  no proxy from the environment.
- **Limits**: 2 MB per page, 15 s per request, HTML or plain text only.
- **Politeness**: robots.txt is respected (RFC 9309: 4xx = allowed, 5xx = everything refused),
  one request per host per second, honest User-Agent pointing to this repository.
- The offer analyst can only read pages of the client's own website.

## Prompt injection (Phase 1, test suite extended in Phase 3)

- Web pages and user descriptions reach the model inside `<untrusted_web_content>` /
  `<untrusted_user_description>` tags; the tags are neutralised inside the content so a page
  cannot "close" them. System prompts state that this content is data, never instructions.
- Agents that read external content have no action tool (no sending, no deletion). Unknown
  tool names are refused by the agent runtime.
- Every claim about a company must quote an excerpt that is really present in a fetched page;
  the check runs in code after the model answers, so page content cannot talk its way past it.

## HTTP hardening (Phase 1)

- API: security headers, `default-src 'none'` CSP on JSON responses, Origin check on
  state-changing requests, per-client rate limit, `Cache-Control: no-store` on `/auth`.
- Web: strict Content-Security-Policy with a per-request nonce for scripts
  (`web/src/proxy.ts`), `X-Frame-Options: DENY`, no `X-Powered-By`.

## Cost safety

- Every LLM call is journaled (tokens, estimated cost in euros, duration, no content).
- Daily budget per workspace: warning at 80 %, LLM work paused at 100 % until the next day or
  a budget increase. Set a spend limit in the Anthropic Console as a second safety net.

## Planned (see [PLAN.md](PLAN.md))

- Encryption at rest (Fernet) of SMTP/IMAP credentials and signed unsubscribe links — Phase 4.
- Dedicated prompt-injection test suite with trapped pages and emails — Phases 3 and 5.
