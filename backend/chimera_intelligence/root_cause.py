"""Deterministic, uncertainty-preserving root-cause interpretation."""

from __future__ import annotations

from .schemas import DetectionIntelligence, IntelligenceAlternative, IntelligenceEvidence, RootCauseIntelligence


_REASON_CAUSES = {
    "expired_method": "EXPIRED_PAYMENT_METHOD",
    "insufficient_funds": "INSUFFICIENT_FUNDS",
    "issuer_decline": "ISSUER_DECLINE",
    "abandonment": "CUSTOMER_ABANDONMENT",
}


def _evidence(field: str, value: object, interpretation: str) -> IntelligenceEvidence:
    return IntelligenceEvidence(field=field, value=str(value), interpretation=interpretation)


def analyze_root_cause(detection: DetectionIntelligence) -> RootCauseIntelligence:
    """Return the most likely operational cause without claiming hidden truth."""

    reason = detection.failure_reason
    evidence: list[IntelligenceEvidence] = []
    contributing: list[str] = []

    if detection.incident_detected:
        primary = "TECHNICAL_INCIDENT"
        confidence = "high" if reason == "technical_degradation" else "medium"
        contributing.append("incident_flag")
        evidence.append(_evidence("incident_flag", True, "A technical incident signal was observable at decision time."))
        if reason == "technical_degradation":
            evidence.append(_evidence("failure_reason", reason, "The observed failure reason is technical degradation."))
    elif reason == "technical_degradation":
        primary = "TECHNICAL_INCIDENT"
        confidence = "medium"
        evidence.append(_evidence("failure_reason", reason, "The observed failure reason indicates a technical degradation."))
    elif reason in _REASON_CAUSES:
        primary = _REASON_CAUSES[reason]
        confidence = "high"
        evidence.append(_evidence("failure_reason", reason, f"The observed failure reason maps to {primary.lower().replace('_', ' ')}."))
    elif detection.observable_history.get("contacts_last_7_days", 0) > 0:
        primary = "CUSTOMER_INACTION"
        confidence = "low"
        contributing.append("prior_contact_history")
        evidence.append(_evidence("contacts_last_7_days", detection.observable_history["contacts_last_7_days"], "Prior outbound contact is observable, but no response is recorded in the case contract."))
    else:
        primary = "UNKNOWN_OR_OTHER"
        confidence = "low"
        evidence.append(_evidence("failure_reason", reason, "The observed failure reason does not identify a more specific operational cause."))

    alternatives: list[IntelligenceAlternative] = []
    if primary != "UNKNOWN_OR_OTHER":
        alternatives.append(IntelligenceAlternative(category="UNKNOWN_OR_OTHER", explanation="Other causes cannot be ruled out from the persisted observable fields."))
    else:
        alternatives.extend([
            IntelligenceAlternative(category="TECHNICAL_INCIDENT", explanation="A technical issue remains possible, but no incident signal is observable."),
            IntelligenceAlternative(category="CUSTOMER_INACTION", explanation="Customer inaction cannot be confirmed without an observable response record."),
        ])

    subject = primary.lower().replace("_", " ")
    statement = f"Observed signals indicate {subject} as the most likely operational cause; hidden causal factors cannot be confirmed."
    return RootCauseIntelligence(
        primary_cause=primary,
        confidence=confidence,
        contributing_factors=contributing,
        evidence=evidence,
        alternatives=alternatives,
        statement=statement,
    )
