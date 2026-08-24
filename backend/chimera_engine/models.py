"""Auditable decision and candidate-score contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CandidateScore:
    action: str
    status: str
    blocked_reason: str | None
    predicted_probability: float
    recoverable_amount_paise: int
    expected_gross_recovery_paise: int
    action_cost_paise: int
    incentive_cost_paise: int
    fatigue_penalty_paise: int
    expected_net_value_paise: int
    expected_net_without_action_cost_paise: int
    expected_net_without_fatigue_paise: int
    rank: int | None
    friction_rank: int
    fatigue_reason: str

    @property
    def permissible(self) -> bool:
        return self.status == "PERMISSIBLE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "predicted_probability": self.predicted_probability,
            "recoverable_amount_paise": self.recoverable_amount_paise,
            "expected_gross_recovery_paise": self.expected_gross_recovery_paise,
            "action_cost_paise": self.action_cost_paise,
            "incentive_cost_paise": self.incentive_cost_paise,
            "fatigue_penalty_paise": self.fatigue_penalty_paise,
            "expected_net_value_paise": self.expected_net_value_paise,
            "expected_net_without_action_cost_paise": self.expected_net_without_action_cost_paise,
            "expected_net_without_fatigue_paise": self.expected_net_without_fatigue_paise,
            "rank": self.rank,
            "friction_rank": self.friction_rank,
            "fatigue_reason": self.fatigue_reason,
        }


@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    event_id: str
    selected_action: str
    candidates: tuple[CandidateScore, ...]
    decision_reason: str
    model_version: str
    feature_schema_version: str
    simulator_version: str
    engine_version: str
    decision_timestamp: datetime
    highest_probability_action: str
    highest_gross_action: str
    highest_net_without_action_cost_action: str
    highest_net_without_fatigue_action: str
    unconstrained_highest_net_action: str
    cost_changed_winner: bool
    fatigue_changed_winner: bool
    constraint_changed_winner: bool
    observable_facts: dict[str, Any]

    def candidate(self, action: str) -> CandidateScore:
        for candidate in self.candidates:
            if candidate.action == action:
                return candidate
        raise KeyError(action)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "event_id": self.event_id,
            "selected_action": self.selected_action,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "decision_reason": self.decision_reason,
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "simulator_version": self.simulator_version,
            "engine_version": self.engine_version,
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "highest_probability_action": self.highest_probability_action,
            "highest_gross_action": self.highest_gross_action,
            "highest_net_without_action_cost_action": self.highest_net_without_action_cost_action,
            "highest_net_without_fatigue_action": self.highest_net_without_fatigue_action,
            "unconstrained_highest_net_action": self.unconstrained_highest_net_action,
            "cost_changed_winner": self.cost_changed_winner,
            "fatigue_changed_winner": self.fatigue_changed_winner,
            "constraint_changed_winner": self.constraint_changed_winner,
            "observable_facts": self.observable_facts,
        }
