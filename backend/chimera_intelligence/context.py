from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.chimera_engine.config import DecisionEngineConfig
from backend.chimera_simulator.config import SimulatorConfig
from backend.chimera_simulator.models import ACTIONS, CONTACT_ACTIONS

from .schemas import SanitizedDecisionContext


def _clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":", 1))
    return hour * 60 + minute


def _contact_window_status(case, simulator_config: SimulatorConfig) -> str:
    defaults = simulator_config.raw["policy_defaults"]
    current = case.decision_timestamp.hour * 60 + case.decision_timestamp.minute
    start = _clock_minutes(defaults["contact_window_start"])
    end = _clock_minutes(defaults["contact_window_end"])
    within = start <= current < end if start <= end else current >= start or current < end
    return "within_configured_window" if within else "outside_configured_window"


def _tie_break_applied(decision, engine_config: DecisionEngineConfig) -> bool:
    permissible = [candidate for candidate in decision.candidates if candidate.status == "PERMISSIBLE"]
    if len(permissible) < 2:
        return False
    highest = max(candidate.expected_net_value_paise for candidate in permissible)
    near_ties = [
        candidate
        for candidate in permissible
        if highest - candidate.expected_net_value_paise <= engine_config.tie_tolerance_paise
    ]
    return len(near_ties) > 1 and decision.selected_action != max(
        near_ties,
        key=lambda candidate: candidate.expected_net_value_paise,
    ).action


def build_intelligence_context(case, decision, simulator_config: SimulatorConfig) -> SanitizedDecisionContext:
    """Construct an allowlisted package from stored decision data only."""

    trace = decision.trace_json if isinstance(decision.trace_json, dict) else {}
    factors = {
        "cost_changed_winner": bool(trace.get("cost_changed_winner", False)),
        "fatigue_changed_winner": bool(trace.get("fatigue_changed_winner", False)),
        "constraint_changed_winner": bool(trace.get("constraint_changed_winner", False)),
        "tie_break_applied": _tie_break_applied(decision, DecisionEngineConfig()),
    }
    context = SanitizedDecisionContext(
        case={
            "case_id": case.id,
            "payment_amount_paise": case.amount_paise,
            "currency": case.currency,
            "failure_reason": case.failure_reason,
            "payment_method": case.payment_method,
            "incident_flag": case.incident_flag,
            "decision_timestamp": case.decision_timestamp,
            "contact_window_status": _contact_window_status(case, simulator_config),
        },
        decision={
            "selected_action": decision.selected_action,
            "predicted_probability": decision.predicted_probability,
            "expected_gross_recovery_paise": decision.expected_gross_recovery_paise,
            "expected_net_value_paise": decision.expected_net_value_paise,
        },
        candidates=[
            {
                "action": candidate.action,
                "predicted_probability": candidate.predicted_probability,
                "expected_net_value_paise": candidate.expected_net_value_paise,
                "action_cost_paise": candidate.action_cost_paise,
                "fatigue_penalty_paise": candidate.fatigue_penalty_paise,
                "status": candidate.status.lower(),
                "blocked_reason": candidate.blocked_reason,
            }
            for candidate in decision.candidates
        ],
        decision_factors=factors,
    )
    if context.decision.selected_action not in ACTIONS:
        raise ValueError("stored decision contains an invalid selected action")
    if len(context.candidates) == 0:
        raise ValueError("stored decision has no candidates")
    return context


def context_json(context: SanitizedDecisionContext) -> dict[str, Any]:
    return context.model_dump(mode="json")
