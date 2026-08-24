"""Deterministic explanation generation from the decision trace."""

from __future__ import annotations

from .models import DecisionResult


def build_explanation(result: DecisionResult) -> str:
    selected = result.candidate(result.selected_action)
    blocked = [candidate for candidate in result.candidates if candidate.blocked_reason]
    parts = [
        f"Selected {result.selected_action} because it had expected net recovery value "
        f"{selected.expected_net_value_paise} paise among permissible actions.",
        f"Its predicted recovery probability was {selected.predicted_probability:.6f}; "
        f"expected gross recovery was {selected.expected_gross_recovery_paise} paise.",
        f"Costs were action={selected.action_cost_paise} paise, "
        f"incentive={selected.incentive_cost_paise} paise, "
        f"fatigue={selected.fatigue_penalty_paise} paise.",
    ]
    if result.observable_facts["incident_flag"]:
        parts.append("The observable incident flag was true.")
    if result.observable_facts["failure_reason"]:
        parts.append(f"The observable failure reason was {result.observable_facts['failure_reason']}.")
    if blocked:
        parts.append(
            "Blocked actions: "
            + ", ".join(f"{candidate.action} ({candidate.blocked_reason})" for candidate in blocked)
            + "."
        )
    if result.highest_probability_action != result.selected_action:
        parts.append(
            f"The highest-probability action was {result.highest_probability_action}, "
            "but expected net value selected the final action."
        )
    if result.cost_changed_winner:
        parts.append("Action costs changed the winning action.")
    if result.fatigue_changed_winner:
        parts.append("Observable fatigue changed the winning action.")
    if result.constraint_changed_winner:
        parts.append("Deterministic constraints changed the winning action.")
    return " ".join(parts)
