"""Prospect state machine (docs/adr/0001-orchestrated-pipeline.md).

    discovered -> contact_found -> email_verified -> researched -> drafted -> qa_passed
    -> awaiting_approval -> scheduled -> sent -> (replied | bounced | unsubscribed | completed)

plus `failed` and `excluded`, always with a reason. Only the transitions listed below are
allowed; every transition is recorded in `prospect_transitions`.
"""

from __future__ import annotations

PROSPECT_STATES: tuple[str, ...] = (
    "discovered",
    "contact_found",
    "email_verified",
    "researched",
    "drafted",
    "qa_passed",
    "awaiting_approval",
    "scheduled",
    "sent",
    "replied",
    "bounced",
    "unsubscribed",
    "completed",
    "failed",
    "excluded",
)

TERMINAL_STATES = frozenset(
    {"replied", "bounced", "unsubscribed", "completed", "failed", "excluded"}
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "discovered": frozenset({"contact_found", "excluded", "failed"}),
    "contact_found": frozenset({"email_verified", "excluded", "failed"}),
    "email_verified": frozenset({"researched", "excluded", "failed"}),
    "researched": frozenset({"drafted", "excluded", "failed"}),
    "drafted": frozenset({"drafted", "qa_passed", "excluded", "failed"}),
    "qa_passed": frozenset({"awaiting_approval", "excluded", "failed"}),
    "awaiting_approval": frozenset({"scheduled", "excluded"}),
    "scheduled": frozenset({"sent", "excluded", "failed"}),
    "sent": frozenset({"replied", "bounced", "unsubscribed", "completed"}),
}


class InvalidTransitionError(ValueError):
    pass


def check_transition(from_state: str, to_state: str, reason: str | None) -> None:
    """Raise if the move is not allowed, or if a failure/exclusion has no reason."""
    if to_state not in ALLOWED_TRANSITIONS.get(from_state, frozenset()):
        raise InvalidTransitionError(f"Transition {from_state} -> {to_state} is not allowed")
    if to_state in {"failed", "excluded"} and not reason:
        raise InvalidTransitionError(f"A transition to {to_state} needs a reason")
