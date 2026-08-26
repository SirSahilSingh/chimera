from __future__ import annotations

from enum import StrEnum

from .errors import InvalidLifecycleTransitionError, TerminalInterventionError


class InterventionStatus(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    AWAITING_OUTCOME = "AWAITING_OUTCOME"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"  # terminal operational record for DO_NOTHING


TERMINAL_STATUSES = frozenset({
    InterventionStatus.RECOVERED,
    InterventionStatus.FAILED,
    InterventionStatus.CANCELLED,
    InterventionStatus.EXPIRED,
    InterventionStatus.COMPLETED,
})


VALID_TRANSITIONS: dict[InterventionStatus, frozenset[InterventionStatus]] = {
    InterventionStatus.CREATED: frozenset({InterventionStatus.QUEUED, InterventionStatus.CANCELLED, InterventionStatus.COMPLETED}),
    InterventionStatus.QUEUED: frozenset({InterventionStatus.READY, InterventionStatus.CANCELLED, InterventionStatus.EXPIRED}),
    InterventionStatus.READY: frozenset({InterventionStatus.EXECUTING, InterventionStatus.CANCELLED, InterventionStatus.EXPIRED}),
    InterventionStatus.EXECUTING: frozenset({InterventionStatus.AWAITING_OUTCOME, InterventionStatus.FAILED}),
    InterventionStatus.AWAITING_OUTCOME: frozenset({InterventionStatus.RECOVERED, InterventionStatus.FAILED, InterventionStatus.EXPIRED}),
    InterventionStatus.RECOVERED: frozenset(),
    InterventionStatus.FAILED: frozenset(),
    InterventionStatus.CANCELLED: frozenset(),
    InterventionStatus.EXPIRED: frozenset(),
    InterventionStatus.COMPLETED: frozenset(),
}


def validate_transition(current: str, target: InterventionStatus) -> None:
    try:
        current_status = InterventionStatus(current)
    except ValueError as exc:
        raise InvalidLifecycleTransitionError(f"unknown intervention status: {current}") from exc
    if current_status in TERMINAL_STATUSES:
        raise TerminalInterventionError(f"terminal intervention cannot transition: {current_status} -> {target}")
    if target not in VALID_TRANSITIONS[current_status]:
        raise InvalidLifecycleTransitionError(f"invalid intervention transition: {current_status} -> {target}")
