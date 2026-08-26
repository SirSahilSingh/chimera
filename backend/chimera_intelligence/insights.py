"""Deterministic explanations and operational insights over persisted records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .diagnosis import parse_timestamp
from .schemas import (
    ConstraintIntelligence,
    DecisionAlternativeIntelligence,
    DecisionIntelligence,
    DetectionIntelligence,
    InterventionIntelligence,
    JourneySummaryIntelligence,
    JourneyTimelineItem,
    OperationalInsight,
    OutcomeIntelligence,
    RootCauseIntelligence,
    StoredExplanationIntelligence,
    VoiceIntelligence,
)


def _trace(journey: Mapping[str, Any]) -> Mapping[str, Any]:
    decision = journey.get("decision") or {}
    value = decision.get("trace_json") if isinstance(decision, Mapping) else {}
    return value if isinstance(value, Mapping) else {}


def build_decision_intelligence(journey: Mapping[str, Any]) -> DecisionIntelligence | None:
    decision = journey.get("decision")
    if not decision:
        return None
    selected = str(decision["selected_action"])
    candidates = decision.get("candidates") or []
    selected_candidate = next((item for item in candidates if item.get("action") == selected), None)
    alternatives: list[DecisionAlternativeIntelligence] = []
    constraints: list[ConstraintIntelligence] = []
    for candidate in candidates:
        if candidate.get("action") == selected:
            continue
        status = str(candidate.get("status", "UNKNOWN"))
        blocked_reason = candidate.get("blocked_reason")
        reason = (
            f"Stored policy result marked this action blocked: {blocked_reason}."
            if blocked_reason
            else "The stored candidate had a lower expected net value than the selected action."
        )
        alternatives.append(DecisionAlternativeIntelligence(
            action=str(candidate["action"]),
            status=status,
            predicted_probability=float(candidate["predicted_probability"]),
            expected_net_value_paise=int(candidate["expected_net_value_paise"]),
            reason_not_selected=reason,
        ))
        if blocked_reason:
            constraints.append(ConstraintIntelligence(action=str(candidate["action"]), reason=str(blocked_reason)))

    trace = _trace(journey)
    highest_probability = trace.get("highest_probability_action")
    net_value = selected_candidate.get("expected_net_value_paise") if selected_candidate else decision.get("expected_net_value_paise")
    summary = f"{selected} was selected by the stored deterministic decision with expected net value {int(net_value)} paise."
    return DecisionIntelligence(
        selected_action=selected,
        decision_summary=summary,
        alternatives=alternatives,
        constraints=constraints,
        cost_affected=bool(trace.get("cost_changed_winner", False)),
        fatigue_affected=bool(trace.get("fatigue_changed_winner", False)),
        constraint_affected=bool(trace.get("constraint_changed_winner", False)),
        highest_probability_action=str(highest_probability) if highest_probability else None,
        highest_probability_action_differed=bool(highest_probability and highest_probability != selected),
    )


def _provider_mode(journey: Mapping[str, Any], intervention: Mapping[str, Any] | None) -> str:
    if intervention:
        executions = intervention.get("executions") or []
        if executions:
            return str(executions[-1].get("provider_mode", "NOT_RECORDED"))
    for key in ("payments", "messages", "retries", "scheduled_retries", "voice_calls", "escalations"):
        records = journey.get(key) or []
        if records:
            return str(records[-1].get("provider_mode", "NOT_RECORDED"))
    return "NOT_EXECUTED"


def _voice_intelligence(journey: Mapping[str, Any], selected_action: str | None, intervention: Mapping[str, Any] | None) -> VoiceIntelligence | None:
    if selected_action != "VOICE_RECOVERY":
        return None
    calls = journey.get("voice_calls") or []
    if not calls:
        return None
    call = calls[-1]
    mode = str(call.get("provider_mode", "NOT_RECORDED"))
    events = call.get("events") or []
    link_requested = any(event.get("event_type") == "PAYMENT_LINK_ATTACHED" for event in events)
    intent = call.get("outcome_intent")
    confirmed_live = mode == "LIVE" and bool(call.get("provider_call_reference"))
    label = "Live voice provider" if confirmed_live else "Demo Voice Agent"
    if mode == "LIVE" and not confirmed_live:
        result = "Live mode is configured, but no confirmed provider call reference is recorded."
    elif intent:
        result = f"Persisted conversation intent: {str(intent).replace('_', ' ').lower()}."
    else:
        result = "Conversation result is not recorded."
    return VoiceIntelligence(
        label=label,
        status=str(call.get("status", "UNKNOWN")),
        provider_mode=mode,
        customer_intent=str(intent) if intent else None,
        conversation_result=result,
        payment_link_requested=link_requested,
        final_intervention_state=str(intervention.get("status", "UNKNOWN")) if intervention else "UNKNOWN",
    )


def build_intervention_intelligence(journey: Mapping[str, Any], selected_action: str | None) -> InterventionIntelligence:
    interventions = journey.get("interventions") or []
    intervention = interventions[-1] if interventions else None
    if intervention is None:
        return InterventionIntelligence(action=selected_action, status="NOT_STARTED", provider_mode="NOT_EXECUTED", execution_summary="No persisted intervention record exists for this case.")
    action = str(intervention.get("action") or selected_action) if intervention.get("action") or selected_action else None
    status = str(intervention.get("status", "UNKNOWN"))
    mode = _provider_mode(journey, intervention)
    executions = intervention.get("executions") or []
    if action == "DO_NOTHING":
        summary = "No external intervention was executed because the stored action was DO_NOTHING."
    elif executions:
        summary = f"The stored {action} intervention has persisted execution status {executions[-1].get('status', status)} in {mode} mode."
    else:
        summary = f"The stored {action} intervention is currently {status}."
    return InterventionIntelligence(
        action=action,
        status=status,
        provider_mode=mode,
        execution_summary=summary,
        voice=_voice_intelligence(journey, selected_action, intervention),
    )


_EVENT_LABELS = {
    "CASE_CREATED": "Payment failure detected",
    "DECISION_COMPLETED": "Deterministic decision stored",
    "INTERVENTION_CREATED": "Recovery intervention created",
    "INTERVENTION_QUEUED": "Intervention queued",
    "INTERVENTION_READY": "Intervention ready",
    "EXECUTION_ACCEPTED": "Intervention accepted by provider boundary",
    "ACTION_EXECUTED": "Intervention executed",
    "PAYMENT_LINK_CREATED": "Payment link generated",
    "RECOVERY_CONFIRMED": "Customer recovery confirmed",
    "RECOVERY_FAILED": "Recovery attempt failed",
    "OUTCOME_RECORDED": "Outcome recorded",
    "ORCHESTRATOR_DO_NOTHING": "No intervention required",
    "ESCALATION_OPENED": "Human escalation opened",
}


def _event_label(event_type: str) -> str:
    return _EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())


def build_journey_summary(journey: Mapping[str, Any], outcome: OutcomeIntelligence) -> JourneySummaryIntelligence:
    decision = journey.get("decision")
    interventions = journey.get("interventions") or []
    case_status = str((journey.get("case") or {}).get("status", "NEW"))
    stages = ["DETECT", "DIAGNOSE"]
    if decision:
        stages.append("DECIDE")
    if interventions:
        stages.append("INTERVENE")
    if outcome.status in {"RECOVERED", "NOT_RECOVERED", "EXPIRED", "DECLINED", "FAILED", "ESCALATED"}:
        stages.append("RECOVER")
        stages.append("LEARN")
    if outcome.status in {"RECOVERED", "NOT_RECOVERED", "EXPIRED", "DECLINED", "FAILED", "ESCALATED"}:
        current = "LEARN"
    elif interventions:
        current = "INTERVENE"
    elif decision:
        current = "DECIDE"
    elif case_status == "NEW":
        current = "DIAGNOSE"
    else:
        current = "DETECT"
    timeline = []
    for event in journey.get("audit_trail") or []:
        timestamp = event.get("timestamp")
        timeline.append(JourneyTimelineItem(
            event_type=str(event.get("event_type", "UNKNOWN")),
            label=_event_label(str(event.get("event_type", "UNKNOWN"))),
            timestamp=parse_timestamp(timestamp) if timestamp else None,
            source=str(event.get("source", "unknown")),
        ))
    return JourneySummaryIntelligence(stages_completed=stages, current_stage=current, timeline=timeline)


def build_explanation_summary(journey: Mapping[str, Any]) -> StoredExplanationIntelligence | None:
    explanation = journey.get("latest_explanation")
    if not explanation:
        return None
    structured = explanation.get("structured_explanation") or {}
    return StoredExplanationIntelligence(
        explanation_source=str(explanation.get("source", "unknown")),
        provider=str(explanation.get("provider", "unknown")),
        model_name=str(explanation.get("model_name", "unknown")),
        generated_at=parse_timestamp(explanation["generated_at"]),
        fallback_reason=explanation.get("fallback_reason"),
        summary=str(structured.get("summary", "Stored explanation has no summary.")),
    )


def build_insights(detection: DetectionIntelligence, diagnosis: RootCauseIntelligence, decision: DecisionIntelligence | None, intervention: InterventionIntelligence, outcome: OutcomeIntelligence) -> list[OperationalInsight]:
    insights = [OperationalInsight(type="failure_category", message=f"The observed failure category is {detection.failure_reason}.")]
    if detection.incident_detected:
        insights.append(OperationalInsight(type="incident_signal", message="An incident flag was present in the observable case context."))
    if decision and decision.constraints:
        insights.append(OperationalInsight(type="constraint_impact", message="One or more candidate actions were unavailable under the stored policy constraints."))
    if decision and decision.cost_affected:
        insights.append(OperationalInsight(type="cost_impact", message="Stored action costs changed the selected winner."))
    if decision and decision.fatigue_affected:
        insights.append(OperationalInsight(type="fatigue_impact", message="Stored customer-fatigue penalties changed the selected winner."))
    if decision and decision.highest_probability_action_differed:
        insights.append(OperationalInsight(type="probability_vs_net_value", message=f"{decision.highest_probability_action} had the highest stored probability, while {decision.selected_action} won on stored expected net value."))
    if intervention.action and intervention.action != "DO_NOTHING":
        insights.append(OperationalInsight(type="intervention_used", message=f"The persisted intervention used {intervention.action}."))
    if outcome.status == "RECOVERED":
        insights.append(OperationalInsight(type="successful_intervention", message="The persisted lifecycle records confirm recovery."))
    elif outcome.status in {"NOT_RECOVERED", "FAILED", "DECLINED", "EXPIRED"}:
        insights.append(OperationalInsight(type="outcome_review", message=f"The persisted lifecycle ended with outcome status {outcome.status}."))
    if outcome.status == "ESCALATED":
        insights.append(OperationalInsight(type="escalation", message="The case has a persisted human escalation record."))
    insights.append(OperationalInsight(type="root_cause_uncertainty", message="Diagnosis is based on observable signals; hidden causal factors are not exposed."))
    return insights
