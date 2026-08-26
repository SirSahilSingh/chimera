"""Read-only outcome analysis over persisted lifecycle records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .diagnosis import parse_timestamp
from .insights import _event_label
from .schemas import OutcomeIntelligence


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _outcomes(journey: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = []
    for intervention in journey.get("interventions") or []:
        rows.extend(intervention.get("outcomes") or [])
    return sorted(rows, key=lambda row: (_aware(parse_timestamp(row["occurred_at"])), str(row.get("id", ""))))


def _executions(journey: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = []
    for intervention in journey.get("interventions") or []:
        rows.extend(intervention.get("executions") or [])
    return rows


def _status(journey: Mapping[str, Any]) -> tuple[str, Mapping[str, Any] | None]:
    case_status = str((journey.get("case") or {}).get("status", "NEW"))
    outcomes = _outcomes(journey)
    latest = outcomes[-1] if outcomes else None
    if case_status == "RECOVERED" or (latest and latest.get("status") == "RECOVERED"):
        return "RECOVERED", latest
    if case_status == "UNRECOVERED" or (latest and latest.get("status") == "NOT_RECOVERED"):
        return "NOT_RECOVERED", latest
    if latest and latest.get("status") in {"EXPIRED", "DECLINED", "FAILED"}:
        return str(latest["status"]), latest
    if any(str(item.get("status")) == "EXPIRED" for item in journey.get("interventions") or []):
        return "EXPIRED", latest
    if any(str(item.get("status")) == "FAILED" for item in journey.get("interventions") or []):
        return "FAILED", latest
    if journey.get("escalations"):
        return "ESCALATED", latest
    if case_status == "PROMISE_TO_PAY_PENDING" or any(str(item.get("status")) == "AWAITING_OUTCOME" for item in journey.get("interventions") or []):
        return "PENDING", latest
    if latest and latest.get("status") == "PENDING":
        return "PENDING", latest
    if any(str(item.get("status")) in {"DECLINED", "FAILED"} for item in _executions(journey)):
        execution = next(item for item in reversed(_executions(journey)) if str(item.get("status")) in {"DECLINED", "FAILED"})
        return str(execution["status"]), latest
    return "PENDING", latest


def _recovery_path(journey: Mapping[str, Any], status: str) -> list[str]:
    path = ["Payment failure detected"]
    for event in journey.get("audit_trail") or []:
        label = _event_label(str(event.get("event_type", "UNKNOWN")))
        if label not in path:
            path.append(label)
    terminal_label = {
        "RECOVERED": "Confirmed recovery",
        "NOT_RECOVERED": "Recovery not confirmed",
        "EXPIRED": "Recovery window expired",
        "DECLINED": "Provider declined the intervention",
        "FAILED": "Intervention failed",
        "ESCALATED": "Human escalation",
    }.get(status)
    if terminal_label and terminal_label not in path:
        path.append(terminal_label)
    return path


def analyze_outcome(journey: Mapping[str, Any], selected_action: str | None) -> OutcomeIntelligence:
    status, latest = _status(journey)
    amount = latest.get("recovered_amount_paise") if status == "RECOVERED" and latest else None
    outcome_timestamp = parse_timestamp(latest["occurred_at"]) if latest and latest.get("occurred_at") else None
    decision_timestamp = parse_timestamp((journey.get("case") or {})["decision_timestamp"])
    time_to_outcome = None
    if outcome_timestamp is not None:
        seconds = int((_aware(outcome_timestamp) - _aware(decision_timestamp)).total_seconds())
        if seconds >= 0:
            time_to_outcome = seconds

    if status == "RECOVERED":
        amount_text = f" for {amount} paise" if amount is not None else ""
        summary = f"The persisted lifecycle confirms recovery{amount_text} after {selected_action or 'the intervention'} .".replace(" .", ".")
    elif status == "NOT_RECOVERED":
        summary = "The selected intervention completed without a confirmed payment recovery."
    elif status == "PENDING":
        summary = "The intervention is still pending; no terminal payment outcome is recorded."
    elif status == "ESCALATED":
        summary = "A human escalation is persisted and remains the current recovery path."
    else:
        summary = f"The persisted lifecycle ended with outcome status {status}."
    return OutcomeIntelligence(
        status=status,
        recovered_amount_paise=amount,
        outcome_timestamp=outcome_timestamp,
        time_to_outcome_seconds=time_to_outcome,
        summary=summary,
        recovery_path=_recovery_path(journey, status),
    )
