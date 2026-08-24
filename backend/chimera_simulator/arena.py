"""Deterministic, file-oriented Recovery Arena evaluation for Gate 2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence

from .config import SimulatorConfig
from .models import ACTIONS, CONTACT_ACTIONS, GeneratedCase, PaymentFailureEvent
from .policies import DeterministicPolicy, PolicySelection
from .seeds import validate_split_seed
from .serialization import event_to_jsonable
from .simulator import Simulator


class InvalidPolicyActionError(ValueError):
    """Raised when a policy selects an action unavailable for the event."""


def _inr_from_paise(value_paise: int) -> float:
    """Create display-only INR values; all calculations remain in integer paise."""

    return value_paise / 100.0


def _observable_context_ref(event: PaymentFailureEvent) -> str:
    payload = json.dumps(event_to_jsonable(event), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _event_parts(event_id: str) -> tuple[str, str, int, int]:
    version, split, seed_text, index_text = event_id.split(":")
    return version, split, int(seed_text), int(index_text)


def _clock_minutes(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":")
        hour, minute = int(hour_text), int(minute_text)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"invalid contact-window time: {value!r}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid contact-window time: {value!r}")
    return hour * 60 + minute


def _contact_window_violation(event: PaymentFailureEvent, action: str) -> bool:
    """Measure outbound timing violations without blocking the selected action."""

    if not event.action_is_outbound.get(action, False) or action not in CONTACT_ACTIONS:
        return False
    start = _clock_minutes(event.contact_window.start_local)
    end = _clock_minutes(event.contact_window.end_local)
    current = event.context.hour * 60
    if start <= end:
        return not (start <= current < end)
    return not (current >= start or current < end)


@dataclass(frozen=True)
class PolicyDecisionRecord:
    event_id: str
    simulator_version: str
    split: str
    seed: int
    event_index: int
    policy_name: str
    action: str
    decision_timestamp: datetime
    observable_context_ref: str
    reason: str
    outcome_status: str
    recovered: bool
    recovered_amount_paise: int
    selected_action_probability: float
    action_cost_paise: int
    incentive_cost_paise: int
    fatigue_penalty_paise: int
    total_intervention_cost_paise: int
    net_recovery_value_paise: int
    policy_violation: bool
    contact_window_violation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "simulator_version": self.simulator_version,
            "split": self.split,
            "seed": self.seed,
            "event_index": self.event_index,
            "policy_name": self.policy_name,
            "action": self.action,
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "observable_context_ref": self.observable_context_ref,
            "reason": self.reason,
            "outcome": self.outcome_status,
            "outcome_status": self.outcome_status,
            "recovered": self.recovered,
            "recovered_amount_paise": self.recovered_amount_paise,
            "recovered_amount_inr": _inr_from_paise(self.recovered_amount_paise),
            "selected_action_probability": self.selected_action_probability,
            "action_cost_paise": self.action_cost_paise,
            "incentive_cost_paise": self.incentive_cost_paise,
            "fatigue_penalty_paise": self.fatigue_penalty_paise,
            "total_intervention_cost_paise": self.total_intervention_cost_paise,
            "total_intervention_cost_inr": _inr_from_paise(self.total_intervention_cost_paise),
            "net_recovery_value_paise": self.net_recovery_value_paise,
            "net_recovery_value_inr": _inr_from_paise(self.net_recovery_value_paise),
            "policy_violation": self.policy_violation,
            "contact_window_violation": self.contact_window_violation,
        }


@dataclass
class _PolicyAccumulator:
    total_events: int = 0
    recovered_events: int = 0
    recovered_amount_paise: int = 0
    total_action_cost_paise: int = 0
    total_incentive_cost_paise: int = 0
    total_fatigue_penalty_paise: int = 0
    total_intervention_cost_paise: int = 0
    gross_recovered_value_paise: int = 0
    net_recovery_value_paise: int = 0
    selected_probability_total: float = 0.0
    policy_violations: int = 0
    contact_window_violations: int = 0
    action_counts: dict[str, int] = field(default_factory=lambda: {action: 0 for action in ACTIONS})

    def add(self, record: PolicyDecisionRecord) -> None:
        self.total_events += 1
        self.recovered_events += int(record.recovered)
        self.recovered_amount_paise += record.recovered_amount_paise
        self.total_action_cost_paise += record.action_cost_paise
        self.total_incentive_cost_paise += record.incentive_cost_paise
        self.total_fatigue_penalty_paise += record.fatigue_penalty_paise
        self.total_intervention_cost_paise += record.total_intervention_cost_paise
        self.gross_recovered_value_paise += record.recovered_amount_paise
        self.net_recovery_value_paise += record.net_recovery_value_paise
        self.selected_probability_total += record.selected_action_probability
        self.policy_violations += int(record.policy_violation)
        self.contact_window_violations += int(record.contact_window_violation)
        self.action_counts[record.action] += 1

    def to_dict(self) -> dict[str, Any]:
        recovery_rate = self.recovered_events / self.total_events if self.total_events else 0.0
        action_distribution = {
            action: (count / self.total_events * 100.0 if self.total_events else 0.0)
            for action, count in self.action_counts.items()
        }
        return {
            "total_events": self.total_events,
            "recovered_events": self.recovered_events,
            "recovery_rate": recovery_rate,
            "recovery_rate_percent": recovery_rate * 100.0,
            "mean_selected_action_probability": (
                self.selected_probability_total / self.total_events if self.total_events else 0.0
            ),
            "recovered_amount_paise": self.recovered_amount_paise,
            "recovered_amount_inr": _inr_from_paise(self.recovered_amount_paise),
            "total_action_cost_paise": self.total_action_cost_paise,
            "total_incentive_cost_paise": self.total_incentive_cost_paise,
            "total_fatigue_penalty_paise": self.total_fatigue_penalty_paise,
            "total_intervention_cost_paise": self.total_intervention_cost_paise,
            "total_intervention_cost_inr": _inr_from_paise(self.total_intervention_cost_paise),
            "gross_recovered_value_paise": self.gross_recovered_value_paise,
            "gross_recovered_value_inr": _inr_from_paise(self.gross_recovered_value_paise),
            "net_recovery_value_paise": self.net_recovery_value_paise,
            "net_recovery_value_inr": _inr_from_paise(self.net_recovery_value_paise),
            "action_counts": dict(self.action_counts),
            "action_distribution_percent": action_distribution,
            "policy_violations": self.policy_violations,
            "contact_window_violations": self.contact_window_violations,
        }


def _aggregate_values(values: Sequence[float | int]) -> dict[str, float]:
    return {
        "mean": mean(values) if values else 0.0,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "stddev": pstdev(values) if len(values) > 1 else 0.0,
    }


def _aggregate_metric_dicts(metric_dicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not metric_dicts:
        return {}
    result: dict[str, Any] = {}
    for key, value in metric_dicts[0].items():
        if isinstance(value, dict):
            result[key] = {
                nested_key: _aggregate_values([float(metrics[key][nested_key]) for metrics in metric_dicts])
                for nested_key in value
            }
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = _aggregate_values([float(metrics[key]) for metrics in metric_dicts])
    return result


@dataclass(frozen=True)
class ArenaReport:
    metadata: dict[str, Any]
    batch_hashes: dict[str, str]
    same_event_batch_across_policies: bool
    per_seed_results: dict[str, dict[str, dict[str, Any]]]
    aggregate_results: dict[str, dict[str, Any]]
    sample_traces: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "batch_hashes": self.batch_hashes,
            "same_event_batch_across_policies": self.same_event_batch_across_policies,
            "per_seed_results": self.per_seed_results,
            "aggregate_results": self.aggregate_results,
            "sample_traces": self.sample_traces,
        }


class ArenaRunner:
    """Run each policy against one shared, pre-generated batch per seed."""

    def __init__(self, config: SimulatorConfig | None = None) -> None:
        self.config = config

    def run(
        self,
        simulator: Simulator,
        split: str,
        seeds: Iterable[int],
        count_per_seed: int,
        policies: Iterable[DeterministicPolicy],
    ) -> ArenaReport:
        seed_list = list(seeds)
        if not seed_list:
            raise ValueError("at least one seed is required")
        if len(set(seed_list)) != len(seed_list):
            raise ValueError("seeds must be unique")
        if isinstance(count_per_seed, bool) or not isinstance(count_per_seed, int) or count_per_seed <= 0:
            raise ValueError("count_per_seed must be a positive integer")
        policy_list = list(policies)
        if not policy_list:
            raise ValueError("at least one policy is required")
        policy_names = [policy.name for policy in policy_list]
        if len(set(policy_names)) != len(policy_names):
            raise ValueError("policy names must be unique")
        if self.config is not None and self.config.config_hash != simulator.config.config_hash:
            raise ValueError("Arena config must match the simulator config")

        for seed in seed_list:
            validate_split_seed(simulator.config, split, seed)

        per_seed_results: dict[str, dict[str, dict[str, Any]]] = {}
        batch_hashes: dict[str, str] = {}
        first_traces: dict[str, dict[str, Any]] = {}
        for seed in seed_list:
            cases = simulator.generate_batch(split, seed, count_per_seed)
            batch_hashes[str(seed)] = self._batch_hash(cases)
            for policy in policy_list:
                metrics, decisions = self._evaluate_cases(cases, policy, simulator.config.simulator_version)
                per_seed_results.setdefault(str(seed), {})[policy.name] = {
                    "metrics": metrics.to_dict(),
                    "decisions": [decision.to_dict() for decision in decisions],
                }
                if policy.name not in first_traces and decisions:
                    first_traces[policy.name] = decisions[0].to_dict()

        aggregate_results: dict[str, dict[str, Any]] = {}
        for policy in policy_list:
            metrics_by_seed = [per_seed_results[str(seed)][policy.name]["metrics"] for seed in seed_list]
            aggregate_results[policy.name] = _aggregate_metric_dicts(metrics_by_seed)

        metadata = {
            "simulator_version": simulator.config.simulator_version,
            "config_hash": simulator.config.config_hash,
            "split": split,
            "seeds": seed_list,
            "count_per_seed": count_per_seed,
            "total_events": len(seed_list) * count_per_seed,
            "policies": policy_names,
            "aggregation": "mean/min/max/population_stddev across seed-level metrics",
            "outcome_resolution": "policy action is selected before the simulator outcome is read",
        }
        return ArenaReport(
            metadata=metadata,
            batch_hashes=batch_hashes,
            same_event_batch_across_policies=True,
            per_seed_results=per_seed_results,
            aggregate_results=aggregate_results,
            sample_traces=first_traces,
        )

    @staticmethod
    def _batch_hash(cases: Sequence[GeneratedCase]) -> str:
        payload = json.dumps(
            [event_to_jsonable(case.event) for case in cases], sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _evaluate_cases(
        cases: Sequence[GeneratedCase], policy: DeterministicPolicy, simulator_version: str
    ) -> tuple[_PolicyAccumulator, list[PolicyDecisionRecord]]:
        metrics = _PolicyAccumulator()
        decisions: list[PolicyDecisionRecord] = []
        for case in cases:
            event = case.event
            selection: PolicySelection = policy.choose_action(event)
            action = selection.selected_action
            if action not in event.available_actions:
                raise InvalidPolicyActionError(
                    f"policy {policy.name} selected unavailable action {action!r} for {event.event_id}"
                )
            _, split, seed, event_index = _event_parts(event.event_id)
            # This is the first point at which simulator truth is read after the policy choice.
            outcome = case.outcome.for_action(action)
            total_cost = outcome.action_cost_paise + outcome.incentive_cost_paise + outcome.fatigue_penalty_paise
            recovered_amount = event.amount_paise if outcome.recovered else 0
            net_value = recovered_amount - total_cost
            decision = PolicyDecisionRecord(
                event_id=event.event_id,
                simulator_version=simulator_version,
                split=split,
                seed=seed,
                event_index=event_index,
                policy_name=policy.name,
                action=action,
                decision_timestamp=event.decision_timestamp,
                observable_context_ref=_observable_context_ref(event),
                reason=selection.reason,
                outcome_status=outcome.status,
                recovered=outcome.recovered,
                recovered_amount_paise=recovered_amount,
                selected_action_probability=outcome.recovery_probability,
                action_cost_paise=outcome.action_cost_paise,
                incentive_cost_paise=outcome.incentive_cost_paise,
                fatigue_penalty_paise=outcome.fatigue_penalty_paise,
                total_intervention_cost_paise=total_cost,
                net_recovery_value_paise=net_value,
                policy_violation=False,
                contact_window_violation=_contact_window_violation(event, action),
            )
            decisions.append(decision)
            metrics.add(decision)
        return metrics, decisions
