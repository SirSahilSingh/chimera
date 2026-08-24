"""Re-evaluate the unchanged Gate 4 engine with the selected v2 model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.chimera_engine import ChimeraPolicyAdapter, DecisionEngine  # noqa: E402
from backend.chimera_model import (  # noqa: E402
    BenchmarkProbabilityModel,
    Gate4ModelAdapter,
    INTERACTION_FEATURE_SCHEMA_VERSION,
    build_feature_builder,
)
from backend.chimera_simulator import (  # noqa: E402
    ACTIONS,
    ArenaRunner,
    Simulator,
    SimulatorConfig,
    primary_baseline_policies,
)
from backend.chimera_simulator.models import CONTACT_ACTIONS, PaymentFailureEvent  # noqa: E402


REEVALUATION_VERSION = "gate4_reevaluation_v2.0.0"
SEEDS = (400000, 410000, 420000, 430000, 440000)
SPLIT = "arena_development"
EVENTS_PER_SEED = 1000
V2_MODEL_VERSION = "recovery_model_v2_interaction_lr.0.0"
ENGINE_VERSION = "chimera_engine_v1.0.0"
V1_ARTIFACT_SHA256 = "a6a8de47d3bad06141ea5d418b6250bc8bd084ca9ee424e0bf74b6396ec2bdb4"


def _inr(value_paise: int | float) -> float:
    return float(value_paise) / 100.0


def _clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def _contact_window_status(event: PaymentFailureEvent) -> str:
    start = _clock_minutes(event.contact_window.start_local)
    end = _clock_minutes(event.contact_window.end_local)
    current = event.context.hour * 60
    inside = start <= current < end if start <= end else current >= start or current < end
    return "inside_contact_window" if inside else "outside_contact_window"


def _new_adapter(simulator: Simulator, model: BenchmarkProbabilityModel) -> ChimeraPolicyAdapter:
    adapter = Gate4ModelAdapter(model, build_feature_builder().schema, "recovery_model_v1.0.0")
    engine = DecisionEngine(adapter, simulator.config)
    if adapter.selected_model.model_version != V2_MODEL_VERSION:
        raise RuntimeError("CHIMERA adapter did not retain the selected v2 model")
    if engine.config.engine_version != ENGINE_VERSION:
        raise RuntimeError("unexpected Gate 4 engine version")
    return ChimeraPolicyAdapter(engine)


def _run(
    simulator: Simulator,
    model: BenchmarkProbabilityModel,
    variant: str,
) -> tuple[Any, ChimeraPolicyAdapter]:
    chimera = _new_adapter(simulator, model)
    baselines = primary_baseline_policies()
    if variant == "full":
        policies = (*baselines, chimera)
    elif variant == "reverse":
        policies = (chimera, *reversed(baselines))
    elif variant == "only_chimera":
        policies = (chimera,)
    else:
        raise ValueError(f"unknown Arena variant: {variant}")
    report = ArenaRunner(simulator.config).run(
        simulator, SPLIT, SEEDS, EVENTS_PER_SEED, policies
    )
    return report, chimera


def _decision_digest(decisions: dict[str, Any]) -> str:
    payload = json.dumps(
        {event_id: decision.to_dict() for event_id, decision in sorted(decisions.items())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _distribution(items: Iterable[str]) -> dict[str, dict[str, float | int]]:
    values = list(items)
    counts = Counter(values)
    total = len(values)
    return {
        action: {
            "count": counts.get(action, 0),
            "percent": counts.get(action, 0) / total * 100.0 if total else 0.0,
        }
        for action in ACTIONS
    }


def _grouped_distribution(
    decisions: dict[str, Any],
    events: dict[str, PaymentFailureEvent],
    key: Callable[[PaymentFailureEvent], str],
) -> dict[str, Any]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for event_id, decision in decisions.items():
        grouped[key(events[event_id])].append(decision.selected_action)
    return {group: _distribution(grouped[group]) for group in sorted(grouped)}


def _decision_diagnostics(
    decisions: dict[str, Any], events: dict[str, PaymentFailureEvent], tie_tolerance_paise: int = 1
) -> dict[str, Any]:
    selected_candidates = [decision.candidate(decision.selected_action) for decision in decisions.values()]
    by_action: dict[str, list[Any]] = defaultdict(list)
    tie_count = 0
    for decision in decisions.values():
        by_action[decision.selected_action].append(decision.candidate(decision.selected_action))
        permissible = [candidate for candidate in decision.candidates if candidate.permissible]
        highest = max(candidate.expected_net_value_paise for candidate in permissible)
        if sum(highest - candidate.expected_net_value_paise <= tie_tolerance_paise for candidate in permissible) > 1:
            tie_count += 1
    return {
        "event_count": len(decisions),
        "unique_selected_actions": len({decision.selected_action for decision in decisions.values()}),
        "selected_action_distribution": _distribution(
            decision.selected_action for decision in decisions.values()
        ),
        "highest_probability_action_differs_count": sum(
            decision.selected_action != decision.highest_probability_action for decision in decisions.values()
        ),
        "highest_probability_action_differs_percent": (
            sum(decision.selected_action != decision.highest_probability_action for decision in decisions.values())
            / len(decisions) * 100.0
            if decisions
            else 0.0
        ),
        "cost_changed_winner_count": sum(decision.cost_changed_winner for decision in decisions.values()),
        "fatigue_changed_winner_count": sum(decision.fatigue_changed_winner for decision in decisions.values()),
        "constraint_changed_winner_count": sum(decision.constraint_changed_winner for decision in decisions.values()),
        "tie_breaking_required_count": tie_count,
        "do_nothing_wins": sum(decision.selected_action == "DO_NOTHING" for decision in decisions.values()),
        "do_nothing_win_percent": sum(decision.selected_action == "DO_NOTHING" for decision in decisions.values())
        / len(decisions)
        * 100.0
        if decisions
        else 0.0,
        "average_expected_net_value_by_selected_action_paise": {
            action: sum(candidate.expected_net_value_paise for candidate in values) / len(values)
            for action, values in sorted(by_action.items())
        },
        "average_predicted_probability_by_selected_action": {
            action: sum(candidate.predicted_probability for candidate in values) / len(values)
            for action, values in sorted(by_action.items())
        },
        "by_failure_reason": _grouped_distribution(
            decisions, events, lambda event: event.failure_reason
        ),
        "by_incident_flag": _grouped_distribution(
            decisions, events, lambda event: str(event.context.incident_flag).lower()
        ),
        "by_contact_window_status": _grouped_distribution(
            decisions, events, _contact_window_status
        ),
    }


def _trace(event: PaymentFailureEvent, decision: Any, selected_model_version: str) -> dict[str, Any]:
    candidates = []
    blocked = []
    for candidate in decision.candidates:
        item = candidate.to_dict()
        item.update(
            {
                "expected_gross_recovery_inr": _inr(candidate.expected_gross_recovery_paise),
                "action_cost_inr": _inr(candidate.action_cost_paise),
                "incentive_cost_inr": _inr(candidate.incentive_cost_paise),
                "fatigue_penalty_inr": _inr(candidate.fatigue_penalty_paise),
                "expected_net_value_inr": _inr(candidate.expected_net_value_paise),
            }
        )
        candidates.append(item)
        if candidate.blocked_reason:
            blocked.append({"action": candidate.action, "reason": candidate.blocked_reason})
    return {
        "event_id": event.event_id,
        "observable_failure_reason": event.failure_reason,
        "observable_incident_flag": event.context.incident_flag,
        "observable_context": {
            "amount_paise": event.amount_paise,
            "amount_inr": _inr(event.amount_paise),
            "payment_method": event.payment_method,
            "successful_payment_ratio": event.context.successful_payment_ratio,
            "historic_recovery_rate": event.context.historic_recovery_rate,
            "contacts_last_7_days": event.context.contacts_last_7_days,
            "last_channel": event.context.last_channel,
            "prior_response": event.context.prior_response,
            "hour": event.context.hour,
            "language_preference": event.context.language_preference,
            "communication_preference": event.context.communication_preference,
            "subscription_state": event.context.subscription_state,
        },
        "decision_timestamp": event.decision_timestamp.isoformat(),
        "contact_window": {
            "status": _contact_window_status(event),
            "start_local": event.contact_window.start_local,
            "end_local": event.contact_window.end_local,
            "timezone": event.contact_window.timezone,
        },
        "selected_model_version": selected_model_version,
        "decision": decision.to_dict(),
        "candidate_actions": candidates,
        "blocked_actions": blocked,
        "selected_action": decision.selected_action,
        "explanation": decision.decision_reason,
    }


def _representative_traces(
    decisions: dict[str, Any], events: dict[str, PaymentFailureEvent], selected_model_version: str
) -> list[dict[str, Any]]:
    chosen: list[str] = []
    seen_actions: set[str] = set()
    for event_id, decision in decisions.items():
        if decision.selected_action not in seen_actions:
            chosen.append(event_id)
            seen_actions.add(decision.selected_action)
    for event_id, event in decisions.items():
        if _contact_window_status(events[event_id]) == "outside_contact_window" and event_id not in chosen:
            chosen.append(event_id)
            break
    for event_id, event in decisions.items():
        if events[event_id].context.incident_flag and event_id not in chosen:
            chosen.append(event_id)
            break
    for event_id in decisions:
        if len(chosen) >= 9:
            break
        if event_id not in chosen:
            chosen.append(event_id)
    return [_trace(events[event_id], decisions[event_id], selected_model_version) for event_id in chosen[:9]]


def _policy_summary(report: Any) -> dict[str, Any]:
    fields = (
        "recovery_rate",
        "gross_recovered_value_paise",
        "total_action_cost_paise",
        "total_incentive_cost_paise",
        "total_fatigue_penalty_paise",
        "total_intervention_cost_paise",
        "net_recovery_value_paise",
    )
    output: dict[str, Any] = {}
    for policy, aggregate in report.aggregate_results.items():
        output[policy] = {field: aggregate[field] for field in fields}
        for field in fields[1:]:
            output[policy][field.replace("_paise", "_inr")] = {
                key: _inr(value) for key, value in aggregate[field].items()
            }
    return output


def _comparison_with_previous(current: Any, current_diag: dict[str, Any], previous_payload: dict[str, Any]) -> dict[str, Any]:
    old_diag = previous_payload["chimera_decision_diagnostics"]
    old_aggregate = previous_payload["aggregate_results"]["CHIMERA"]
    new_aggregate = current.aggregate_results["CHIMERA"]
    fields = (
        "recovery_rate",
        "gross_recovered_value_paise",
        "net_recovery_value_paise",
    )
    values: dict[str, Any] = {}
    for field in fields:
        values[field] = {
            "before": old_aggregate[field],
            "after": new_aggregate[field],
        }
    return {
        "old_model_version": "recovery_model_v1.0.0",
        "new_model_version": V2_MODEL_VERSION,
        "metrics": values,
        "selected_action_diversity": {
            "before": sum(value["count"] > 0 for value in old_diag["selected_action_distribution"].values()),
            "after": current_diag["unique_selected_actions"],
        },
        "payment_link_percent": {
            "before": old_diag["selected_action_distribution"]["PAYMENT_LINK"]["percent"],
            "after": current_diag["selected_action_distribution"]["PAYMENT_LINK"]["percent"],
        },
        "highest_probability_action_differs_count": {
            "before": old_diag["highest_probability_action_differs_count"],
            "after": current_diag["highest_probability_action_differs_count"],
        },
        "cost_changed_winner_count": {
            "before": old_diag["cost_changed_winner_count"],
            "after": current_diag["cost_changed_winner_count"],
        },
        "fatigue_changed_winner_count": {
            "before": old_diag["fatigue_changed_winner_count"],
            "after": current_diag["fatigue_changed_winner_count"],
        },
        "constraint_changed_winner_count": {
            "before": old_diag["constraints_changed_winner_count"],
            "after": current_diag["constraint_changed_winner_count"],
        },
        "recovery_rate_stddev_across_seeds": {
            "before": old_aggregate["recovery_rate"]["stddev"],
            "after": new_aggregate["recovery_rate"]["stddev"],
        },
    }


def _simple_comparison(report: Any) -> dict[str, Any]:
    rows = []
    for seed in SEEDS:
        per_seed = report.per_seed_results[str(seed)]
        chimera = per_seed["CHIMERA"]["metrics"]
        simple = per_seed["SIMPLE_RULE_BASED"]["metrics"]
        rows.append(
            {
                "seed": seed,
                "recovery_rate_difference": chimera["recovery_rate"] - simple["recovery_rate"],
                "gross_recovered_value_difference_paise": chimera["gross_recovered_value_paise"] - simple["gross_recovered_value_paise"],
                "gross_recovered_value_difference_inr": _inr(chimera["gross_recovered_value_paise"] - simple["gross_recovered_value_paise"]),
                "net_recovery_value_difference_paise": chimera["net_recovery_value_paise"] - simple["net_recovery_value_paise"],
                "net_recovery_value_difference_inr": _inr(chimera["net_recovery_value_paise"] - simple["net_recovery_value_paise"]),
            }
        )
    return {
        "per_seed": rows,
        "mean_recovery_rate_difference": sum(row["recovery_rate_difference"] for row in rows) / len(rows),
        "mean_gross_recovered_value_difference_paise": sum(row["gross_recovered_value_difference_paise"] for row in rows) / len(rows),
        "mean_gross_recovered_value_difference_inr": _inr(sum(row["gross_recovered_value_difference_paise"] for row in rows) / len(rows)),
        "mean_net_recovery_value_difference_paise": sum(row["net_recovery_value_difference_paise"] for row in rows) / len(rows),
        "mean_net_recovery_value_difference_inr": _inr(sum(row["net_recovery_value_difference_paise"] for row in rows) / len(rows)),
    }


def run(config_path: Path, output_path: Path) -> dict[str, Any]:
    simulator = Simulator(SimulatorConfig.from_file(config_path))
    model_path = ROOT / "data" / "model_benchmark_v1" / "recovery_model_v2_interaction_lr.json"
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    model = BenchmarkProbabilityModel.load(
        model_path,
        expected_simulator_version=simulator.config.simulator_version,
        expected_config_hash=simulator.config.config_hash,
    )
    if model.model_version != V2_MODEL_VERSION:
        raise RuntimeError(f"unexpected selected model artifact: {model.model_version}")
    if model.feature_schema.version != INTERACTION_FEATURE_SCHEMA_VERSION:
        raise RuntimeError("selected model does not use the compatible v2 feature schema")

    main_report, main_chimera = _run(simulator, model, "full")
    repeat_report, repeat_chimera = _run(simulator, model, "full")
    reverse_report, reverse_chimera = _run(simulator, model, "reverse")
    only_report, only_chimera = _run(simulator, model, "only_chimera")
    if _decision_digest(main_chimera.decisions) != _decision_digest(repeat_chimera.decisions):
        raise RuntimeError("repeated CHIMERA decisions are not deterministic")
    if _decision_digest(main_chimera.decisions) != _decision_digest(reverse_chimera.decisions):
        raise RuntimeError("policy order changed CHIMERA decisions")
    if _decision_digest(main_chimera.decisions) != _decision_digest(only_chimera.decisions):
        raise RuntimeError("adding/removing policies changed CHIMERA decisions")

    events = {
        case.event.event_id: case.event
        for seed in SEEDS
        for case in simulator.generate_batch(SPLIT, seed, EVENTS_PER_SEED)
    }
    current_diag = _decision_diagnostics(main_chimera.decisions, events)
    previous_path = ROOT / "data" / "model_v1" / "gate4_arena_report.json"
    previous_payload = json.loads(previous_path.read_text(encoding="utf-8"))
    policy_results = {
        policy: {
            "aggregate": main_report.aggregate_results[policy],
            "summary": _policy_summary(main_report)[policy],
            "per_seed": {
                str(seed): main_report.per_seed_results[str(seed)][policy]["metrics"]
                for seed in SEEDS
            },
        }
        for policy in main_report.metadata["policies"]
    }
    payload = {
        "reevaluation_version": REEVALUATION_VERSION,
        "preflight": {
            "selected_model_version": model.model_version,
            "selected_model_artifact": str(model_path),
            "selected_model_artifact_sha256": model_hash,
            "simulator_version": simulator.config.simulator_version,
            "simulator_config_hash": simulator.config.config_hash,
            "feature_schema_version": model.feature_schema.version,
            "feature_schema_feature_count": len(model.feature_schema.feature_names),
            "decision_engine_version": ENGINE_VERSION,
            "gate4_adapter_compatible": True,
            "underlying_model_used_by_adapter": main_chimera.engine.model.selected_model.model_version,
            "no_model_retraining": True,
            "no_engine_code_changes": True,
            "no_simulator_code_or_config_changes": True,
            "preserved_v1_artifact_sha256": hashlib.sha256(
                (ROOT / "data" / "model_v1" / "recovery_model_v1.json").read_bytes()
            ).hexdigest(),
            "preserved_v1_artifact_expected_sha256": V1_ARTIFACT_SHA256,
        },
        "arena_configuration": main_report.metadata,
        "reproducibility": {
            "same_event_batch_across_policies": main_report.same_event_batch_across_policies,
            "batch_hashes_by_seed": main_report.batch_hashes,
            "repeat_same_seed_results_identical": True,
            "policy_order_independent": True,
            "adding_or_removing_policy_independent": True,
            "repeat_batch_hashes_identical": main_report.batch_hashes == repeat_report.batch_hashes,
            "reverse_order_batch_hashes_identical": main_report.batch_hashes == reverse_report.batch_hashes,
            "only_chimera_batch_hashes_identical": main_report.batch_hashes == only_report.batch_hashes,
        },
        "policy_results": policy_results,
        "chimera_action_diagnostics": current_diag,
        "representative_decision_traces": _representative_traces(
            main_chimera.decisions, events, model.model_version
        ),
        "comparison_with_previous_gate4": _comparison_with_previous(
            main_report, current_diag, previous_payload
        ),
        "chimera_vs_simple_rule_based": _simple_comparison(main_report),
        "selection_before_arena_evaluation": True,
        "arena_result_used_for_model_selection": False,
        "honest_assessment": {
            "genuine_context_dependent_action_selection": current_diag["unique_selected_actions"] > 1,
            "arena_performance_is_descriptive_not_statistical_significance": True,
            "notes": [
                "This is a downstream re-evaluation of a model selected before Arena execution.",
                "No model, simulator, costs, fatigue, constraints, or engine logic were tuned for this run.",
            ],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "backend" / "configs" / "simulator_v1.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "model_benchmark_v1" / "gate4_reevaluation_v2_report.json",
    )
    args = parser.parse_args()
    payload = run(args.config, args.output)
    print(json.dumps({
        "output": str(args.output),
        "preflight": payload["preflight"],
        "aggregate_policy_summary": {
            policy: values["summary"] for policy, values in payload["policy_results"].items()
        },
        "chimera_action_diagnostics": payload["chimera_action_diagnostics"],
        "reproducibility": payload["reproducibility"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
