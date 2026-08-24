from __future__ import annotations

from enum import StrEnum


class CaseStatus(StrEnum):
    NEW = "NEW"
    DECIDED = "DECIDED"
    ACTION_PENDING = "ACTION_PENDING"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    PROMISE_TO_PAY_PENDING = "PROMISE_TO_PAY_PENDING"
    RECOVERED = "RECOVERED"
    UNRECOVERED = "UNRECOVERED"
    CLOSED = "CLOSED"


VALID_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.NEW: frozenset({CaseStatus.DECIDED, CaseStatus.CLOSED}),
    CaseStatus.DECIDED: frozenset({CaseStatus.ACTION_PENDING, CaseStatus.CLOSED}),
    CaseStatus.ACTION_PENDING: frozenset({CaseStatus.ACTION_EXECUTED, CaseStatus.CLOSED}),
    CaseStatus.ACTION_EXECUTED: frozenset({CaseStatus.PROMISE_TO_PAY_PENDING, CaseStatus.RECOVERED, CaseStatus.UNRECOVERED, CaseStatus.CLOSED}),
    CaseStatus.PROMISE_TO_PAY_PENDING: frozenset({CaseStatus.RECOVERED, CaseStatus.UNRECOVERED, CaseStatus.CLOSED}),
    CaseStatus.RECOVERED: frozenset({CaseStatus.CLOSED}),
    CaseStatus.UNRECOVERED: frozenset({CaseStatus.CLOSED}),
    CaseStatus.CLOSED: frozenset(),
}


class DomainError(ValueError):
    pass


def transition(current: str, target: CaseStatus) -> None:
    try:
        current_status = CaseStatus(current)
    except ValueError as exc:
        raise DomainError(f"unknown case status: {current}") from exc
    if target not in VALID_TRANSITIONS[current_status]:
        raise DomainError(f"invalid case transition: {current_status} -> {target}")
