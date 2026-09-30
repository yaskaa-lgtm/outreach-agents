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

## Planned (see [PLAN.md](PLAN.md))

- SSRF protection for every web fetch (private/loopback/link-local IPs refused, redirects
  re-checked, size and time limits) — Phase 1.
- Prompt-injection defences: untrusted content tags, no action tools for agents reading
  external content, trapped-page tests — Phases 1 and 3.
- API rate limiting and a strict Content-Security-Policy — Phase 1.
