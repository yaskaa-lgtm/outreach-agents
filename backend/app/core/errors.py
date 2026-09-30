"""Domain errors, mapped to JSON responses `{"code": ..., "message": ...}` in `app.main`."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class: a stable machine-readable `code`, a human message, an HTTP status."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"


class TooManyAttemptsError(AppError):
    status_code = 429
    code = "too_many_attempts"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class LLMNotConfiguredError(AppError):
    status_code = 503
    code = "llm_not_configured"


class LLMBudgetExhaustedError(AppError):
    """The daily LLM budget is used up: LLM work is paused, not failed."""

    status_code = 429
    code = "llm_budget_exhausted"


class AgentError(AppError):
    """An agent could not produce a valid result (refusal, invalid output, too many steps)."""

    status_code = 502
    code = "agent_failed"


class FetchError(AppError):
    """A web page could not be fetched safely (SSRF guard, robots.txt, size, type...)."""

    status_code = 422
    code = "fetch_failed"
