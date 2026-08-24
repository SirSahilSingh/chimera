from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

from backend.chimera_simulator import (
    ACTIONS,
    CONTACT_ACTIONS,
    ConfigurationError,
    Simulator,
    SimulatorConfig,
    is_within_horizon,
)
from backend.chimera_simulator.context import build_observable_context
from backend.chimera_simulator.models import ContactEvent, HistoricalPayment
from backend.chimera_simulator.serialization import truth_to_jsonable
from backend.chimera_simulator.seeds import InvalidSeedError


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend" / "configs" / "simulator_v1.yaml"


class SimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig.from_file(CONFIG_PATH)
        cls.simulator = Simulator(cls.config)

    def test_deterministic_reproduction(self) -> None:
        first = self.simulator.generate_case("arena_development", 400000, 7)
        second = self.simulator.generate_case("arena_development", 400000, 7)
        self.assertEqual(truth_to_jsonable(first), truth_to_jsonable(second))

    def test_event_identity_is_split_seed_and_index_specific(self) -> None:
        first = self.simulator.generate_case("arena_development", 400000, 0)
        second = self.simulator.generate_case("arena_development", 400000, 1)
        final = self.simulator.generate_case("arena_final", 900000, 0)
        self.assertEqual(first.event.event_id, "simulator_v1.0.0:arena_development:400000:0")
        self.assertNotEqual(first.event.event_id, second.event.event_id)
        self.assertNotEqual(first.event.event_id, final.event.event_id)

    def test_invalid_seed_split_combination_is_rejected(self) -> None:
        with self.assertRaises(InvalidSeedError):
            self.simulator.generate_case("training", 400000, 0)
        with self.assertRaises(InvalidSeedError):
            self.simulator.generate_case("not_a_split", 400000, 0)
        with self.assertRaises(InvalidSeedError):
            self.simulator.generate_case("arena_final", 899999, 0)

    def test_split_ranges_are_disjoint(self) -> None:
        ranges = self.config.raw["seed"]["ranges"]
        for name, (minimum, maximum) in ranges.items():
            for other_name, (other_minimum, other_maximum) in ranges.items():
                if name == other_name:
                    continue
                self.assertTrue(maximum < other_minimum or other_maximum < minimum)

    def test_temporal_cutoff_excludes_future_records(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 2)
        decision_timestamp = case.event.decision_timestamp
        past = HistoricalPayment("past", decision_timestamp - timedelta(days=1), 100, "failed", "synthetic")
        future = HistoricalPayment("future", decision_timestamp + timedelta(seconds=1), 999999, "succeeded", "future")
        past_contact = ContactEvent("past-contact", decision_timestamp - timedelta(hours=1), "message", "read")
        future_contact = ContactEvent("future-contact", decision_timestamp + timedelta(seconds=1), "voice", "willing_to_pay")
        context = build_observable_context(
            case.event.customer,
            [past, future],
            [past_contact, future_contact],
            decision_timestamp,
            incident_flag=False,
        )
        self.assertEqual([item.payment_id for item in context.historical_payments], ["past"])
        self.assertEqual([item.contact_id for item in context.prior_contacts], ["past-contact"])
        self.assertEqual(context.successful_payment_ratio, 0.0)
        self.assertEqual(context.source_timestamp, decision_timestamp)

    def test_future_success_cannot_enter_features(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 3)
        future = HistoricalPayment(
            "future-success",
            case.event.decision_timestamp + timedelta(days=1),
            720000,
            "succeeded",
            "future",
        )
        context = build_observable_context(
            case.event.customer,
            [future],
            [],
            case.event.decision_timestamp,
            incident_flag=False,
        )
        self.assertEqual(context.historical_payments, ())
        self.assertEqual(context.successful_payment_ratio, 0.0)

    def test_hidden_state_is_not_on_decision_facing_event(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 4)
        event_fields = asdict(case.event)
        self.assertNotIn("hidden_state", event_fields)
        self.assertNotIn("customer_segment", event_fields)
        self.assertNotIn("environment_state", event_fields)
        self.assertNotIn("natural_recovery_probability", event_fields)
        self.assertNotIn("action_outcomes", event_fields)
        self.assertTrue(hasattr(case, "hidden_state"))

    def test_environment_is_independent_and_only_incident_proxy_is_observable(self) -> None:
        found_normal = None
        found_degraded = None
        for seed in range(400000, 400050):
            case = self.simulator.generate_case("arena_development", seed, 0)
            if case.hidden_state.environment_state == "NORMAL":
                found_normal = case
            else:
                found_degraded = case
            if found_normal and found_degraded:
                break
        self.assertIsNotNone(found_normal)
        self.assertIsNotNone(found_degraded)
        self.assertFalse(found_normal.event.context.incident_flag)
        self.assertTrue(found_degraded.event.context.incident_flag)
        self.assertNotIn("environment_state", asdict(found_degraded.event.context))

    def test_action_probabilities_are_bounded_and_complete(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 5)
        self.assertEqual(case.event.available_actions, ACTIONS)
        self.assertEqual(tuple(result.action for result in case.outcome.action_outcomes), ACTIONS)
        for result in case.outcome.action_outcomes:
            self.assertGreaterEqual(result.recovery_probability, 0.01)
            self.assertLessEqual(result.recovery_probability, 0.99)

    def test_seven_day_boundary_is_half_open(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 6)
        start = case.outcome.horizon_start
        end = case.outcome.horizon_end
        self.assertTrue(is_within_horizon(start, start, end))
        self.assertTrue(is_within_horizon(end - timedelta(microseconds=1), start, end))
        self.assertFalse(is_within_horizon(end, start, end))

    def test_promise_to_pay_state_and_boundary(self) -> None:
        case = None
        for index in range(100):
            candidate = self.simulator.generate_case("arena_development", 400000, index)
            if not candidate.outcome.for_action("VOICE_RECOVERY").recovered:
                case = candidate
                break
        self.assertIsNotNone(case)
        promised_date = case.outcome.horizon_start + timedelta(days=2)
        updated = self.simulator.apply_promise_to_pay(case, promised_date)
        voice = updated.outcome.for_action("VOICE_RECOVERY")
        self.assertEqual(voice.status, "PROMISE_TO_PAY_PENDING")
        self.assertFalse(voice.recovered)
        self.assertTrue(voice.outreach_paused)
        self.assertEqual(voice.verification_timestamp, promised_date)
        with self.assertRaises(ValueError):
            self.simulator.apply_promise_to_pay(case, case.outcome.horizon_end)

    def test_contact_window_is_metadata_not_action_blocking(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 8)
        self.assertEqual(set(case.event.contact_window.contact_actions), set(CONTACT_ACTIONS))
        self.assertFalse(case.event.action_is_outbound["RETRY_NOW"])
        self.assertFalse(case.event.action_is_outbound["RETRY_LATER"])
        self.assertFalse(case.event.action_is_outbound["DO_NOTHING"])
        self.assertTrue(case.event.action_is_outbound["SEND_MESSAGE"])
        self.assertTrue(case.event.action_is_outbound["VOICE_RECOVERY"])
        self.assertTrue(case.event.action_is_outbound["HUMAN_OUTREACH"])

    def test_all_money_is_integer_paise(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 9)
        self.assertIsInstance(case.event.amount_paise, int)
        self.assertNotIsInstance(case.event.amount_paise, bool)
        for result in case.outcome.action_outcomes:
            for value in (result.action_cost_paise, result.incentive_cost_paise, result.fatigue_penalty_paise):
                self.assertIsInstance(value, int)
                self.assertNotIsInstance(value, bool)
        self.assertEqual(10000000, 100000 * 100)

    def test_synthetic_identifiers_are_used(self) -> None:
        case = self.simulator.generate_case("arena_development", 400000, 10)
        self.assertTrue(case.event.customer.synthetic_email.endswith("@example.test"))
        self.assertTrue(case.event.customer.synthetic_phone.startswith("+91-90000-"))

    def test_configuration_hash_and_loading(self) -> None:
        self.assertEqual(len(self.config.config_hash), 64)
        self.assertEqual(self.config.simulator_version, "simulator_v1.0.0")
        self.assertEqual(self.config.horizon_days, 7)

    def test_invalid_configuration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid_path = Path(directory) / "invalid.yaml"
            invalid_path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                SimulatorConfig.from_file(invalid_path)

            invalid_money_path = Path(directory) / "invalid-money.yaml"
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            raw["costs_paise"]["action"]["RETRY_NOW"] = 0.5
            invalid_money_path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                SimulatorConfig.from_file(invalid_money_path)

    def test_diagnostics_cover_required_outputs(self) -> None:
        from backend.chimera_simulator.diagnostics import build_diagnostics

        diagnostics = build_diagnostics(self.simulator.generate_batch("arena_development", 400000, 25))
        self.assertEqual(diagnostics["event_count"], 25)
        self.assertEqual(set(diagnostics["recovery_probability_by_action"]), set(ACTIONS))
        self.assertIn("lower_0.01", diagnostics["probability_clamp_percentages"])
        self.assertIn("upper_0.99", diagnostics["probability_clamp_percentages"])
        self.assertEqual(set(diagnostics["action_cost_distribution_paise"]), set(ACTIONS))
        self.assertEqual(set(diagnostics["best_action_distribution"]["actions"]), set(ACTIONS))
        self.assertEqual(set(diagnostics["root_cause_x_action"]), {case.event.failure_reason for case in self.simulator.generate_batch("arena_development", 400000, 25)})
        self.assertTrue(diagnostics["customer_segment_x_action"])
        self.assertEqual(set(diagnostics["incident_flag_x_action"]), {"true", "false"})
        self.assertTrue(diagnostics["environment_x_action_internal"])
        self.assertTrue(diagnostics["root_cause_x_customer_segment_best_action"])
        self.assertIn("combinations", diagnostics["lower_clamp_analysis"])


if __name__ == "__main__":
    unittest.main()
