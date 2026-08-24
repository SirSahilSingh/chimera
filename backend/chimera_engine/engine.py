"""Deterministic CHIMERA expected-net-value decision engine."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterable

from backend.chimera_model.features import ObservableFeatureBuilder
from backend.chimera_model.model import ModelCompatibilityError, RecoveryProbabilityModel
from backend.chimera_simulator.config import SimulatorConfig
from backend.chimera_simulator.models import ACTIONS, PaymentFailureEvent

from .config import DecisionEngineConfig
from .constraints import evaluate_constraints
from .explanations import build_explanation
from .fatigue import calculate_fatigue_penalty_paise
from .models import CandidateScore, DecisionResult


class DecisionEngineCompatibilityError(ModelCompatibilityError):
    """Raised when the model/config/schema cannot safely be used by the engine."""


def _round_half_up_paise(probability: float, amount_paise: int) -> int:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be within [0, 1]")
    if isinstance(amount_paise, bool) or not isinstance(amount_paise, int) or amount_paise < 0:
        raise ValueError("amount_paise must be a non-negative integer")
    product = Decimal(str(probability)) * Decimal(amount_paise)
    return int(product.to_integral_value(rounding=ROUND_HALF_UP))


class DecisionEngine:
    """Select the highest expected-net-value permissible action."""

    def __init__(
        self,
        model: RecoveryProbabilityModel,
        simulator_config: SimulatorConfig,
        engine_config: DecisionEngineConfig | None = None,
    ) -> None:
        self.model = model
        self.simulator_config = simulator_config
        self.config = engine_config or DecisionEngineConfig()
        self.config.validate()
        self._validate_compatibility()
        self.feature_builder = ObservableFeatureBuilder(model.feature_schema)
        self._action_order = {action: index for index, action in enumerate(ACTIONS)}
        self._friction_order = {
            action: index for index, action in enumerate(self.config.friction_order)
        }

    def _validate_compatibility(self) -> None:
        if self.model.model_version != self.config.compatible_model_version:
            raise DecisionEngineCompatibilityError("incompatible model version")
        if self.model.simulator_version != self.config.compatible_simulator_version:
            raise DecisionEngineCompatibilityError("incompatible model simulator version")
        if self.model.simulator_config_hash != self.simulator_config.config_hash:
            raise DecisionEngineCompatibilityError("model simulator configuration hash does not match active config")
        if self.model.feature_schema.version != self.config.compatible_feature_schema_version:
            raise DecisionEngineCompatibilityError("incompatible model feature schema version")

    def _highest(
        self,
        candidates: Iterable[CandidateScore],
        value: Callable[[CandidateScore], int | float],
        permissible_only: bool,
    ) -> CandidateScore:
        selected = [candidate for candidate in candidates if candidate.permissible or not permissible_only]
        if not selected:
            raise ValueError("no candidates available for comparison")
        return max(
            selected,
            key=lambda candidate: (value(candidate), -self._action_order[candidate.action]),
        )

    def _select_permissible(self, candidates: list[CandidateScore]) -> CandidateScore:
        permissible = [candidate for candidate in candidates if candidate.permissible]
        if not permissible:
            raise ValueError("no permissible action remains")
        highest_value = max(candidate.expected_net_value_paise for candidate in permissible)
        near_ties = [
            candidate
            for candidate in permissible
            if highest_value - candidate.expected_net_value_paise <= self.config.tie_tolerance_paise
        ]
        return min(
            near_ties,
            key=lambda candidate: (
                candidate.friction_rank,
                candidate.action_cost_paise,
                self._action_order[candidate.action],
            ),
        )

    def decide(self, event: PaymentFailureEvent) -> DecisionResult:
        self.feature_builder.validate_event(event)
        candidates: list[CandidateScore] = []
        for action in ACTIONS:
            constraints = evaluate_constraints(event, action)
            # Unavailable actions are visible in the trace but are not sent to
            # the model because the observable event declares them invalid.
            probability = (
                self.model.predict_probability(event, action, self.feature_builder)
                if action in event.available_actions
                else 0.0
            )
            recoverable_amount = event.amount_paise
            gross = _round_half_up_paise(probability, recoverable_amount)
            action_cost = self.simulator_config.action_costs_paise[action]
            incentive_cost = self.simulator_config.incentive_costs_paise[action]
            fatigue, fatigue_reason = calculate_fatigue_penalty_paise(
                event, action, self.simulator_config.fatigue_base_paise
            )
            net = gross - action_cost - incentive_cost - fatigue
            candidates.append(
                CandidateScore(
                    action=action,
                    status="PERMISSIBLE" if constraints.permissible else "BLOCKED",
                    blocked_reason=constraints.reason,
                    predicted_probability=probability,
                    recoverable_amount_paise=recoverable_amount,
                    expected_gross_recovery_paise=gross,
                    action_cost_paise=action_cost,
                    incentive_cost_paise=incentive_cost,
                    fatigue_penalty_paise=fatigue,
                    expected_net_value_paise=net,
                    expected_net_without_action_cost_paise=gross - incentive_cost - fatigue,
                    expected_net_without_fatigue_paise=gross - action_cost - incentive_cost,
                    rank=None,
                    friction_rank=self._friction_order[action],
                    fatigue_reason=fatigue_reason,
                )
            )

        selected = self._select_permissible(candidates)
        permissible = [candidate for candidate in candidates if candidate.permissible]
        ranked = sorted(
            permissible,
            key=lambda candidate: (
                -candidate.expected_net_value_paise,
                candidate.friction_rank,
                candidate.action_cost_paise,
                self._action_order[candidate.action],
            ),
        )
        rank_map = {selected.action: 1}
        next_rank = 2
        for candidate in ranked:
            if candidate.action != selected.action:
                rank_map[candidate.action] = next_rank
                next_rank += 1
        candidates = [replace(candidate, rank=rank_map.get(candidate.action)) for candidate in candidates]

        highest_probability = self._highest(candidates, lambda candidate: candidate.predicted_probability, False)
        highest_gross = self._highest(candidates, lambda candidate: candidate.expected_gross_recovery_paise, True)
        highest_without_action = self._highest(
            candidates, lambda candidate: candidate.expected_net_without_action_cost_paise, True
        )
        highest_without_fatigue = self._highest(
            candidates, lambda candidate: candidate.expected_net_without_fatigue_paise, True
        )
        unconstrained_highest_net = self._highest(
            candidates, lambda candidate: candidate.expected_net_value_paise, False
        )
        decision_id = hashlib.sha256(
            "|".join(
                (
                    self.config.engine_version,
                    self.model.model_version,
                    self.model.feature_schema.version,
                    self.simulator_config.config_hash,
                    event.event_id,
                    selected.action,
                )
            ).encode("utf-8")
        ).hexdigest()
        facts = {
            "failure_reason": event.failure_reason,
            "incident_flag": event.context.incident_flag,
            "hour": event.context.hour,
            "contacts_last_7_days": event.context.contacts_last_7_days,
            "available_actions": list(event.available_actions),
            "contact_window_start": event.contact_window.start_local,
            "contact_window_end": event.contact_window.end_local,
            "contact_window_timezone": event.contact_window.timezone,
        }
        result = DecisionResult(
            decision_id=decision_id,
            event_id=event.event_id,
            selected_action=selected.action,
            candidates=tuple(candidates),
            decision_reason="",
            model_version=self.model.model_version,
            feature_schema_version=self.model.feature_schema.version,
            simulator_version=self.model.simulator_version,
            engine_version=self.config.engine_version,
            decision_timestamp=event.decision_timestamp,
            highest_probability_action=highest_probability.action,
            highest_gross_action=highest_gross.action,
            highest_net_without_action_cost_action=highest_without_action.action,
            highest_net_without_fatigue_action=highest_without_fatigue.action,
            unconstrained_highest_net_action=unconstrained_highest_net.action,
            cost_changed_winner=highest_without_action.action != selected.action,
            fatigue_changed_winner=highest_without_fatigue.action != selected.action,
            constraint_changed_winner=unconstrained_highest_net.action != selected.action,
            observable_facts=facts,
        )
        return replace(result, decision_reason=build_explanation(result))
