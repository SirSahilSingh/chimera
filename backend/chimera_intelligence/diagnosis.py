"""Observable-only detection for the persisted recovery intelligence view."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .schemas import DetectionIntelligence


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":", 1))
    return hour * 60 + minute


def contact_window_status(timestamp: datetime, simulator_config: Any) -> str:
    defaults = simulator_config.raw["policy_defaults"]
    current = timestamp.hour * 60 + timestamp.minute
    start = _clock_minutes(defaults["contact_window_start"])
    end = _clock_minutes(defaults["contact_window_end"])
    within = start <= current < end if start <= end else current >= start or current < end
    return "within_configured_window" if within else "outside_configured_window"


def _observable_history(journey: Mapping[str, Any]) -> dict[str, int | None]:
    decision = journey.get("decision") or {}
    trace = decision.get("trace_json") if isinstance(decision, Mapping) else {}
    facts = trace.get("observable_facts") if isinstance(trace, Mapping) else {}
    facts = facts if isinstance(facts, Mapping) else {}
    history: dict[str, int | None] = {}
    for key in ("contacts_last_7_days", "prior_retry_count"):
        value = facts.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            history[key] = value
    return history


def _severity(case: Mapping[str, Any]) -> str:
    if case["incident_flag"] or case["amount_paise"] >= 100_000:
        return "high"
    if case["status"] != "NEW" or case["amount_paise"] >= 25_000:
        return "medium"
    return "low"


def build_detection(journey: Mapping[str, Any], simulator_config: Any) -> DetectionIntelligence:
    """Build a deterministic problem summary from stored observable fields."""

    case = journey["case"]
    timestamp = parse_timestamp(case["decision_timestamp"])
    window_status = contact_window_status(timestamp, simulator_config)
    incident = bool(case["incident_flag"])
    reason = str(case["failure_reason"])
    incident_phrase = "during a technical incident" if incident else "in the observed payment context"
    return DetectionIntelligence(
        problem_type="payment_failure",
        failure_reason=reason,
        payment_method=str(case["payment_method"]),
        incident_detected=incident,
        failure_timestamp=timestamp,
        amount_at_risk_paise=int(case["amount_paise"]),
        contact_window_status=window_status,
        outbound_contact_eligible=window_status == "within_configured_window",
        current_recovery_state=str(case["status"]),
        severity=_severity(case),
        observable_history=_observable_history(journey),
        summary=f"Payment recovery failure detected {incident_phrase}.",
    )
