"""CHIMERA decision diagnostics for development Arena review."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from backend.chimera_simulator.models import ACTIONS

from .models import DecisionResult


def _example(result: DecisionResult) -> dict[str, Any]:
    return {
        "event_id": result.event_id,
        "selected_action": result.selected_action,
        "highest_probability_action": result.highest_probability_action,
        "highest_gross_action": result.highest_gross_action,
        "highest_net_without_action_cost_action": result.highest_net_without_action_cost_action,
        "highest_net_without_fatigue_action": result.highest_net_without_fatigue_action,
        "unconstrained_highest_net_action": result.unconstrained_highest_net_action,
        "decision_reason": result.decision_reason,
    }


def summarize_decisions(decisions: Iterable[DecisionResult]) -> dict[str, Any]:
    items = list(decisions)
    if not items:
        return {"event_count": 0}
    selected = Counter(item.selected_action for item in items)
    blocked = Counter(
        candidate.action
        for item in items
        for candidate in item.candidates
        if candidate.blocked_reason
    )
    blocked_reasons = Counter(
        candidate.blocked_reason
        for item in items
        for candidate in item.candidates
        if candidate.blocked_reason
    )
    selected_candidates = [item.candidate(item.selected_action) for item in items]
    distribution = {
        action: {"count": selected.get(action, 0), "percent": selected.get(action, 0) / len(items) * 100.0}
        for action in ACTIONS
    }
    return {
        "event_count": len(items),
        "selected_action_distribution": distribution,
        "blocked_action_counts": dict(blocked),
        "blocked_reasons": dict(blocked_reasons),
        "do_nothing_wins": selected.get("DO_NOTHING", 0),
        "do_nothing_win_rate": selected.get("DO_NOTHING", 0) / len(items),
        "highest_probability_action_differs_count": sum(
            item.highest_probability_action != item.selected_action for item in items
        ),
        "highest_probability_action_differs_rate": sum(
            item.highest_probability_action != item.selected_action for item in items
        )
        / len(items),
        "average_predicted_probability_selected_action": sum(
            candidate.predicted_probability for candidate in selected_candidates
        )
        / len(selected_candidates),
        "average_expected_net_value_selected_action_paise": sum(
            candidate.expected_net_value_paise for candidate in selected_candidates
        )
        / len(selected_candidates),
        "cost_changed_winner_count": sum(item.cost_changed_winner for item in items),
        "fatigue_changed_winner_count": sum(item.fatigue_changed_winner for item in items),
        "constraints_changed_winner_count": sum(item.constraint_changed_winner for item in items),
        "examples_cost_changed_winner": [_example(item) for item in items if item.cost_changed_winner][:3],
        "examples_fatigue_changed_winner": [_example(item) for item in items if item.fatigue_changed_winner][:3],
        "examples_constraints_changed_winner": [_example(item) for item in items if item.constraint_changed_winner][:3],
    }
