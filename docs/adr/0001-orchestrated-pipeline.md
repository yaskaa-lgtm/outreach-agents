# ADR 0001 — Orchestrated pipeline instead of a free-roaming agent

- Status: accepted
- Date: 2026-09-30

## Context

The product must prospect autonomously: understand the client's offer, define target
segments, find companies and decision makers, research each prospect, write emails, send
them after human approval, and handle replies. Two broad designs exist:

1. **One autonomous agent** with many tools that decides by itself what to do next.
2. **An orchestrated pipeline**: a deterministic state machine moves each campaign and each
   prospect from step to step, and each step calls one specialised agent with a strict role,
   a minimal tool set and a validated output format.

The domain has hard constraints: no hallucinated facts in emails, no email without human
approval, suppression list always enforced, legal rules (CNIL / GDPR), controlled costs.

## Decision

Use an **orchestrated pipeline**.

- The prospect lifecycle is an explicit state machine:
  `discovered → contact_found → email_verified → researched → drafted → qa_passed →
  awaiting_approval → scheduled → sent → (replied | bounced | unsubscribed | completed)`,
  plus `failed` and `excluded` with a reason. Every transition is recorded.
- Each step is a job in a PostgreSQL queue, idempotent and retryable.
- Each agent has a versioned system prompt, a typed input, a Pydantic-validated output
  (one retry with the validation error, then a clean failure) and only the tools it needs.
- Compliance checks (suppression list, webmail blocklist, footer, unsubscribe headers) are
  **plain code**, executed at fixed points of the state machine — never left to an LLM.

## Consequences

Positive:
- **Reliability**: the LLM never decides whether to send an email or skip a compliance check.
- **Testability**: each step can be tested alone with a deterministic `FakeLLM`; the state
  machine can be tested without any LLM.
- **Debuggability**: every prospect has a state, a history of transitions and the
  `llm_calls` / `provider_calls` logs of each step.
- **Cost control**: each step uses the cheapest suitable model and can be budgeted.
- **Security**: agents that read untrusted content (web pages, inbound emails) have no
  action tools, which limits the impact of prompt injection.

Negative:
- Less flexible than a free agent: a new capability needs a new step or agent.
- More code up front (state machine, job queue, schemas).

These trade-offs are acceptable: in this domain, predictability matters more than autonomy.
