from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from backend.chimera_engine import DecisionEngine, DecisionEngineConfig
from backend.chimera_engine.engine import DecisionEngineCompatibilityError
from backend.chimera_engine.policy import ChimeraPolicyAdapter
from backend.chimera_model import FeatureSchema, build_feature_builder
from backend.chimera_simulator import ACTIONS, Simulator, SimulatorConfig
from backend.chimera_simulator.models import PaymentFailureEvent
from backend.chimera_simulator.policies import PolicySelection


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend" / "configs" / "simulator_v1.yaml"


class StubProbabilityModel:
    model_version = "recovery_model_v1.0.0"
    simulator_version = "simulator_v1.0.0"

    def __init__(self, simulator_config, feature_schema, resolver):
        self.simulator_config_hash = simulator_config.config_hash
        self.feature_schema = feature_schema
        self.resolver = resolver

    def predict_probability(self, event, candidate_action, feature_builder=None):
        return float(self.resolver(event, candidate_action))


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig.from_file(CONFIG_PATH)
        cls.simulator = Simulator(cls.config)
        cls.builder = build_feature_builder()

    def _engine(self, resolver, model_overrides=None, engine_config=None):
        model = StubProbabilityModel(self.config, self.builder.schema, resolver)
        for key, value in (model_overrides or {}).items():
            setattr(model, key, value)
        return DecisionEngine(model, self.config, engine_config)

    def test_highest_probability_does_not_necessarily_win(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event

        def resolver(current_event, action):
            if action == "VOICE_RECOVERY":
                return 0.90
            if action == "PAYMENT_LINK":
                return 0.90 - 1000.0 / current_event.amount_paise
            return 0.10

        decision = self._engine(resolver).decide(event)
        self.assertEqual(decision.highest_probability_action, "VOICE_RECOVERY")
        self.assertEqual(decision.selected_action, "PAYMENT_LINK")
        self.assertGreater(
            decision.candidate("PAYMENT_LINK").expected_net_value_paise,
            decision.candidate("VOICE_RECOVERY").expected_net_value_paise,
        )

    def test_do_nothing_can_win(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event
        decision = self._engine(lambda _event, action: 0.80 if action == "DO_NOTHING" else 0.10).decide(event)
        self.assertEqual(decision.selected_action, "DO_NOTHING")
        self.assertEqual(decision.candidate("DO_NOTHING").expected_net_value_paise, decision.candidate("DO_NOTHING").expected_gross_recovery_paise)

    def test_outbound_actions_are_blocked_outside_contact_window(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 500).event
        decision = self._engine(lambda _event, _action: 0.50).decide(event)
        for action in ("SEND_MESSAGE", "VOICE_RECOVERY"):
            candidate = decision.candidate(action)
            self.assertEqual(candidate.status, "BLOCKED")
            self.assertEqual(candidate.blocked_reason, "outside_contact_window")
        for action in ("RETRY_NOW", "RETRY_LATER", "DO_NOTHING"):
            self.assertEqual(decision.candidate(action).status, "PERMISSIBLE")

    def test_blocked_actions_remain_in_trace(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 500).event
        decision = self._engine(lambda _event, _action: 0.50).decide(event)
        self.assertEqual(tuple(candidate.action for candidate in decision.candidates), ACTIONS)
        self.assertTrue(all(decision.candidate(action).blocked_reason for action in ("SEND_MESSAGE", "VOICE_RECOVERY")))

    def test_fatigue_changes_action_ranking(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event

        def resolver(current_event, action):
            if action == "RETRY_NOW":
                return 0.60
            if action == "PAYMENT_LINK":
                return 0.60 + 1.0 / current_event.amount_paise
            return 0.05

        no_contacts = replace(event, context=replace(event.context, contacts_last_7_days=0))
        many_contacts = replace(event, context=replace(event.context, contacts_last_7_days=5))
        engine = self._engine(resolver)
        self.assertEqual(engine.decide(no_contacts).selected_action, "PAYMENT_LINK")
        self.assertEqual(engine.decide(many_contacts).selected_action, "RETRY_NOW")

    def test_action_cost_changes_action_ranking(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event
        decision = self._engine(
            lambda _event, action: 0.60 if action in {"RETRY_NOW", "PAYMENT_LINK"} else 0.05
        ).decide(event)
        self.assertEqual(decision.candidate("RETRY_NOW").expected_gross_recovery_paise, decision.candidate("PAYMENT_LINK").expected_gross_recovery_paise)
        self.assertEqual(decision.selected_action, "PAYMENT_LINK")

    def test_tie_breaking_is_deterministic_and_prefers_lower_friction(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event

        def resolver(current_event, action):
            if action == "DO_NOTHING":
                return 0.50
            if action == "RETRY_NOW":
                return float((Decimal(current_event.amount_paise) * Decimal("0.50") + Decimal(500)) / Decimal(current_event.amount_paise))
            return 0.05

        engine = self._engine(resolver)
        first = engine.decide(event)
        second = engine.decide(event)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.selected_action, "DO_NOTHING")
        self.assertLessEqual(
            abs(
                first.candidate("DO_NOTHING").expected_net_value_paise
                - first.candidate("RETRY_NOW").expected_net_value_paise
            ),
            1,
        )

    def test_unavailable_action_is_blocked_and_rejected_from_model_scoring(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event
        restricted = replace(event, available_actions=tuple(action for action in ACTIONS if action != "ESCALATE"))
        decision = self._engine(lambda _event, _action: 0.5).decide(restricted)
        self.assertEqual(decision.candidate("ESCALATE").status, "BLOCKED")
        self.assertEqual(decision.candidate("ESCALATE").blocked_reason, "unavailable_action")

    def test_all_candidate_expected_values_are_consistent(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 500).event
        decision = self._engine(lambda _event, _action: 0.37).decide(event)
        for candidate in decision.candidates:
            expected_gross = int(
                (Decimal(str(candidate.predicted_probability)) * Decimal(event.amount_paise)).to_integral_value(
                    rounding=ROUND_HALF_UP
                )
            )
            self.assertEqual(candidate.expected_gross_recovery_paise, expected_gross)
            self.assertEqual(
                candidate.expected_net_value_paise,
                candidate.expected_gross_recovery_paise
                - candidate.action_cost_paise
                - candidate.incentive_cost_paise
                - candidate.fatigue_penalty_paise,
            )

    def test_explanation_uses_trace_facts_only(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 500).event
        decision = self._engine(lambda _event, _action: 0.50).decide(event)
        self.assertIn(decision.selected_action, decision.decision_reason)
        self.assertIn(event.failure_reason, decision.decision_reason)
        self.assertIn("outside_contact_window", decision.decision_reason)
        self.assertNotIn("customer segment", decision.decision_reason.lower())
        self.assertNotIn("environment state", decision.decision_reason.lower())

    def test_compatibility_rejects_model_schema_and_simulator_mismatches(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event
        with self.assertRaises(DecisionEngineCompatibilityError):
            self._engine(lambda _event, _action: 0.5, {"model_version": "recovery_model_v9.0.0"})
        incompatible_schema = FeatureSchema(
            version="features_v9.0.0",
            feature_names=self.builder.schema.feature_names,
            allowed_source_fields=self.builder.schema.allowed_source_fields,
            forbidden_source_fields=self.builder.schema.forbidden_source_fields,
        )
        with self.assertRaises(DecisionEngineCompatibilityError):
            DecisionEngine(
                StubProbabilityModel(self.config, incompatible_schema, lambda _event, _action: 0.5),
                self.config,
            )
        with self.assertRaises(DecisionEngineCompatibilityError):
            self._engine(lambda _event, _action: 0.5, {"simulator_version": "simulator_v9.0.0"})

    def test_chimera_policy_adapter_exposes_arena_interface(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 0).event
        adapter = ChimeraPolicyAdapter(self._engine(lambda _event, _action: 0.5))
        selection = adapter.choose_action(event)
        self.assertIsInstance(selection, PolicySelection)
        self.assertEqual(selection.selected_action, adapter.decisions[event.event_id].selected_action)


if __name__ == "__main__":
    unittest.main()
