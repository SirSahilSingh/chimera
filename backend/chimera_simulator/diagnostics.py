"""Distribution diagnostics for generated simulator batches."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Iterable

from .models import ACTIONS, GeneratedCase

DIAGNOSTIC_TIE_EPSILON = 1e-12
DIAGNOSTIC_NEAR_TIE_EPSILON = 0.01


def _distribution(values: Iterable[str]) -> dict[str, Any]:
    counts = Counter(values)
    total = sum(counts.values())
    return {
        key: {"count": count, "share": count / total if total else 0.0}
        for key, count in sorted(counts.items())
    }


def _event_action_probabilities(case: GeneratedCase) -> dict[str, float]:
    return {action: case.outcome.for_action(action).recovery_probability for action in ACTIONS}


def _event_best_action(case: GeneratedCase) -> tuple[str, bool, bool]:
    probabilities = _event_action_probabilities(case)
    ordered = sorted(probabilities.items(), key=lambda item: (-item[1], ACTIONS.index(item[0])))
    top_probability = ordered[0][1]
    exact_ties = [action for action, probability in ordered if abs(probability - top_probability) <= DIAGNOSTIC_TIE_EPSILON]
    near_tie = len(ordered) > 1 and top_probability - ordered[1][1] <= DIAGNOSTIC_NEAR_TIE_EPSILON
    return ordered[0][0], len(exact_ties) > 1, near_tie


def _group_report(cases: tuple[GeneratedCase, ...]) -> dict[str, Any]:
    action_metrics: dict[str, dict[str, Any]] = {}
    mean_probabilities: dict[str, float] = {}
    for action in ACTIONS:
        results = [case.outcome.for_action(action) for case in cases]
        values = [result.recovery_probability for result in results]
        mean_probability = mean(values) if values else 0.0
        mean_probabilities[action] = mean_probability
        action_metrics[action] = {
            "event_count": len(results),
            "mean_probability": mean_probability,
            "realized_recovery_rate_percent": 100.0 * sum(result.recovered for result in results) / len(results)
            if results
            else 0.0,
        }
    highest_probability = max(mean_probabilities.values(), default=0.0)
    highest_actions = [
        action
        for action in ACTIONS
        if abs(mean_probabilities[action] - highest_probability) <= DIAGNOSTIC_TIE_EPSILON
    ]
    exact_tie_count = 0
    near_tie_count = 0
    for case in cases:
        _, exact_tie, near_tie = _event_best_action(case)
        exact_tie_count += exact_tie
        near_tie_count += near_tie
    count = len(cases)
    return {
        "event_count": count,
        "actions": action_metrics,
        "highest_probability_action": highest_actions,
        "exact_tie_event_count": exact_tie_count,
        "exact_tie_frequency_percent": 100.0 * exact_tie_count / count if count else 0.0,
        "near_tie_event_count": near_tie_count,
        "near_tie_frequency_percent": 100.0 * near_tie_count / count if count else 0.0,
    }


def _group_cases(cases: tuple[GeneratedCase, ...], key_function: Any) -> dict[str, tuple[GeneratedCase, ...]]:
    grouped: dict[str, list[GeneratedCase]] = defaultdict(list)
    for case in cases:
        grouped[key_function(case)].append(case)
    return {key: tuple(value) for key, value in sorted(grouped.items())}


def _breakdown(cases: tuple[GeneratedCase, ...], key_function: Any) -> dict[str, Any]:
    return {key: _group_report(group) for key, group in _group_cases(cases, key_function).items()}


def _best_action_distribution(cases: tuple[GeneratedCase, ...]) -> dict[str, Any]:
    counts = Counter()
    exact_tie_count = 0
    near_tie_count = 0
    for case in cases:
        action, exact_tie, near_tie = _event_best_action(case)
        counts[action] += 1
        exact_tie_count += exact_tie
        near_tie_count += near_tie
    total = len(cases)
    return {
        "tie_threshold": DIAGNOSTIC_TIE_EPSILON,
        "near_tie_threshold": DIAGNOSTIC_NEAR_TIE_EPSILON,
        "actions": {
            action: {
                "count": counts[action],
                "share_percent": 100.0 * counts[action] / total if total else 0.0,
            }
            for action in ACTIONS
        },
        "exact_tie_event_count": exact_tie_count,
        "exact_tie_frequency_percent": 100.0 * exact_tie_count / total if total else 0.0,
        "near_tie_event_count": near_tie_count,
        "near_tie_frequency_percent": 100.0 * near_tie_count / total if total else 0.0,
    }


def _lower_clamp_analysis(cases: tuple[GeneratedCase, ...]) -> dict[str, Any]:
    combinations: Counter[tuple[str, str, str, str]] = Counter()
    total_probabilities = len(cases) * len(ACTIONS)
    for case in cases:
        for action in ACTIONS:
            result = case.outcome.for_action(action)
            if result.recovery_probability == 0.01:
                combinations[
                    (
                        case.event.failure_reason,
                        case.hidden_state.customer_segment,
                        case.hidden_state.environment_state,
                        action,
                    )
                ] += 1
    total_hits = sum(combinations.values())
    return {
        "total_hits": total_hits,
        "total_probabilities": total_probabilities,
        "percentage_of_all_probabilities": 100.0 * total_hits / total_probabilities
        if total_probabilities
        else 0.0,
        "combinations": [
            {
                "root_cause": root_cause,
                "customer_segment": segment,
                "environment": environment,
                "action": action,
                "count": count,
                "share_of_lower_clamp_hits_percent": 100.0 * count / total_hits if total_hits else 0.0,
            }
            for (root_cause, segment, environment, action), count in sorted(combinations.items())
        ],
    }


def build_diagnostics(cases: Iterable[GeneratedCase]) -> dict[str, Any]:
    cases = tuple(cases)
    probabilities = {action: [case.outcome.for_action(action).recovery_probability for case in cases] for action in ACTIONS}
    action_outcomes = {action: [case.outcome.for_action(action) for case in cases] for action in ACTIONS}
    all_probabilities = [probability for values in probabilities.values() for probability in values]
    action_costs = {action: [case.outcome.for_action(action).action_cost_paise for case in cases] for action in ACTIONS}
    result = {
        "event_count": len(cases),
        "segment_distribution": _distribution(case.hidden_state.customer_segment for case in cases),
        "environment_distribution": _distribution(case.hidden_state.environment_state for case in cases),
        "root_cause_distribution": _distribution(case.event.failure_reason for case in cases),
        "recovery_probability_by_action": {
            action: {
                "mean": mean(values) if values else 0.0,
                "min": min(values) if values else 0.0,
                "max": max(values) if values else 0.0,
            }
            for action, values in probabilities.items()
        },
        "probability_clamp_percentages": {
            "lower_0.01": 100.0 * sum(value == 0.01 for value in all_probabilities) / len(all_probabilities)
            if all_probabilities
            else 0.0,
            "upper_0.99": 100.0 * sum(value == 0.99 for value in all_probabilities) / len(all_probabilities)
            if all_probabilities
            else 0.0,
        },
        "seven_day_recovery_rate_by_action": {
            action: 100.0 * sum(result.recovered for result in results) / len(results) if results else 0.0
            for action, results in action_outcomes.items()
        },
        "action_cost_distribution_paise": {
            action: {
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "mean": mean(values) if values else 0.0,
            }
            for action, values in action_costs.items()
        },
    }
    result["best_action_distribution"] = _best_action_distribution(cases)
    result["root_cause_x_action"] = _breakdown(cases, lambda case: case.event.failure_reason)
    result["customer_segment_x_action"] = _breakdown(cases, lambda case: case.hidden_state.customer_segment)
    result["incident_flag_x_action"] = _breakdown(cases, lambda case: str(case.event.context.incident_flag).lower())
    result["environment_x_action_internal"] = _breakdown(cases, lambda case: case.hidden_state.environment_state)
    result["root_cause_x_customer_segment_best_action"] = {
        root_cause: {
            segment: _group_report(group)
            for segment, group in _group_cases(
                root_cases,
                lambda case: case.hidden_state.customer_segment,
            ).items()
        }
        for root_cause, root_cases in _group_cases(cases, lambda case: case.event.failure_reason).items()
    }
    result["lower_clamp_analysis"] = _lower_clamp_analysis(cases)
    return result
