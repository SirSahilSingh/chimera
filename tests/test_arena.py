from __future__ import annotations

import unittest
from pathlib import Path

from backend.chimera_simulator import (
    ACTIONS,
    ArenaRunner,
    InvalidPolicyActionError,
    InvalidSeedError,
    PolicySelection,
    Simulator,
    SimulatorConfig,
    primary_baseline_policies,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend" / "configs" / "simulator_v1.yaml"


class CapturePolicy:
    def __init__(self, name: str, action: str = "DO_NOTHING") -> None:
        self.name = name
        self.action = action
        self.event_ids: list[str] = []
        self.saw_future_truth = False

    def choose_action(self, event):
        self.event_ids.append(event.event_id)
        self.saw_future_truth = self.saw_future_truth or any(
            hasattr(event, field)
            for field in ("hidden_state", "outcome", "action_outcomes", "customer_segment", "environment_state")
        )
        return PolicySelection(self.action, "test policy")


class InvalidActionPolicy:
    name = "INVALID_ACTION"

    def choose_action(self, event):
        return PolicySelection("NOT_AN_ACTION", "intentional test failure")


class ArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig.from_file(CONFIG_PATH)
        cls.simulator = Simulator(cls.config)

    def test_primary_policies_are_observable_only_and_actions_are_valid(self) -> None:
        report = ArenaRunner(self.config).run(
            self.simulator, "arena_development", [400000], 20, primary_baseline_policies()
        )
        for policy_name, result in report.per_seed_results["400000"].items():
            self.assertEqual(result["metrics"]["policy_violations"], 0, policy_name)
            self.assertEqual(result["metrics"]["total_events"], 20, policy_name)
            self.assertTrue(all(record["action"] in ACTIONS for record in result["decisions"]))

    def test_arena_passes_identical_event_batch_to_each_policy(self) -> None:
        first = CapturePolicy("CAPTURE_ONE")
        second = CapturePolicy("CAPTURE_TWO")
        report = ArenaRunner(self.config).run(self.simulator, "arena_development", [400000], 15, [first, second])
        self.assertEqual(first.event_ids, second.event_ids)
        self.assertEqual(report.same_event_batch_across_policies, True)
        self.assertEqual(len(report.batch_hashes), 1)
        self.assertFalse(first.saw_future_truth)
        self.assertFalse(second.saw_future_truth)

    def test_arena_is_deterministic_for_same_inputs(self) -> None:
        runner = ArenaRunner(self.config)
        first = runner.run(self.simulator, "arena_development", [400000, 410000], 12, primary_baseline_policies())
        second = runner.run(self.simulator, "arena_development", [400000, 410000], 12, primary_baseline_policies())
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_policy_evaluation_order_does_not_change_per_policy_results(self) -> None:
        runner = ArenaRunner(self.config)
        policies = primary_baseline_policies()
        forward = runner.run(self.simulator, "arena_development", [400000], 25, policies)
        reverse = runner.run(self.simulator, "arena_development", [400000], 25, tuple(reversed(policies)))
        for policy in policies:
            self.assertEqual(
                forward.per_seed_results["400000"][policy.name],
                reverse.per_seed_results["400000"][policy.name],
            )
            self.assertEqual(forward.aggregate_results[policy.name], reverse.aggregate_results[policy.name])

    def test_selected_action_uses_its_own_probability_and_counterfactual_draw(self) -> None:
        case = None
        for event_index in range(1000):
            candidate = self.simulator.generate_case("arena_development", 400000, event_index)
            retry = candidate.outcome.for_action("RETRY_NOW")
            link = candidate.outcome.for_action("PAYMENT_LINK")
            if retry.recovery_probability != link.recovery_probability and retry.recovered != link.recovered:
                case = candidate
                break
        self.assertIsNotNone(case)
        retry = case.outcome.for_action("RETRY_NOW")
        link = case.outcome.for_action("PAYMENT_LINK")
        self.assertNotEqual(retry.recovered, link.recovered)

        runner = ArenaRunner(self.config)
        event_count = int(case.event.event_id.rsplit(":", 1)[1]) + 1
        report = runner.run(
            self.simulator,
            "arena_development",
            [400000],
            event_count,
            [CapturePolicy("RETRY_COUNTERFACTUAL", "RETRY_NOW"), CapturePolicy("LINK_COUNTERFACTUAL", "PAYMENT_LINK")],
        )
        retry_record = report.per_seed_results["400000"]["RETRY_COUNTERFACTUAL"]["decisions"][event_count - 1]
        link_record = report.per_seed_results["400000"]["LINK_COUNTERFACTUAL"]["decisions"][event_count - 1]
        self.assertEqual(retry_record["selected_action_probability"], retry.recovery_probability)
        self.assertEqual(link_record["selected_action_probability"], link.recovery_probability)
        self.assertEqual(retry_record["recovered"], retry.recovered)
        self.assertEqual(link_record["recovered"], link.recovered)

    def test_same_event_and_action_resolves_identically_on_repeat(self) -> None:
        first = self.simulator.generate_case("arena_development", 400000, 3)
        second = self.simulator.generate_case("arena_development", 400000, 3)
        for action in ACTIONS:
            self.assertEqual(first.outcome.for_action(action), second.outcome.for_action(action))

    def test_adding_a_policy_does_not_change_existing_policy_results(self) -> None:
        runner = ArenaRunner(self.config)
        baseline = primary_baseline_policies()
        existing = runner.run(self.simulator, "arena_development", [400000], 25, baseline)
        expanded = runner.run(
            self.simulator,
            "arena_development",
            [400000],
            25,
            (*baseline, CapturePolicy("ADDED_POLICY", "DO_NOTHING")),
        )
        for policy in baseline:
            self.assertEqual(
                existing.per_seed_results["400000"][policy.name],
                expanded.per_seed_results["400000"][policy.name],
            )
            self.assertEqual(existing.aggregate_results[policy.name], expanded.aggregate_results[policy.name])

    def test_multi_seed_aggregation_reports_mean_min_max_stddev(self) -> None:
        report = ArenaRunner(self.config).run(
            self.simulator, "arena_development", [400000, 410000, 420000], 10, primary_baseline_policies()
        )
        aggregate = report.aggregate_results["NO_INTERVENTION"]
        for key in ("total_events", "recovered_events", "recovery_rate", "net_recovery_value_paise"):
            self.assertEqual(set(aggregate[key]), {"mean", "min", "max", "stddev"})

    def test_cost_fatigue_and_net_value_are_integer_paise(self) -> None:
        report = ArenaRunner(self.config).run(
            self.simulator, "arena_development", [400000], 20, primary_baseline_policies()
        )
        for record in report.per_seed_results["400000"]["SIMPLE_RULE_BASED"]["decisions"]:
            self.assertIsInstance(record["action_cost_paise"], int)
            self.assertIsInstance(record["incentive_cost_paise"], int)
            self.assertIsInstance(record["fatigue_penalty_paise"], int)
            self.assertEqual(
                record["total_intervention_cost_paise"],
                record["action_cost_paise"] + record["incentive_cost_paise"] + record["fatigue_penalty_paise"],
            )
            self.assertEqual(
                record["net_recovery_value_paise"],
                record["recovered_amount_paise"] - record["total_intervention_cost_paise"],
            )

    def test_do_nothing_has_no_intervention_cost(self) -> None:
        report = ArenaRunner(self.config).run(
            self.simulator, "arena_development", [400000], 20, [CapturePolicy("NO_COST", "DO_NOTHING")]
        )
        metrics = report.per_seed_results["400000"]["NO_COST"]["metrics"]
        self.assertEqual(metrics["total_intervention_cost_paise"], 0)
        self.assertEqual(metrics["total_action_cost_paise"], 0)
        self.assertEqual(metrics["total_fatigue_penalty_paise"], 0)

    def test_outcome_is_resolved_after_policy_choice(self) -> None:
        policy = CapturePolicy("CHOICE_FIRST", "RETRY_LATER")
        report = ArenaRunner(self.config).run(self.simulator, "arena_development", [400000], 1, [policy])
        record = report.per_seed_results["400000"]["CHOICE_FIRST"]["decisions"][0]
        self.assertEqual(record["action"], "RETRY_LATER")
        self.assertIn(record["outcome_status"], {"RECOVERED", "UNRECOVERED"})
        self.assertEqual(record["event_id"], "simulator_v1.0.0:arena_development:400000:0")

    def test_invalid_action_is_rejected_before_outcome_resolution(self) -> None:
        with self.assertRaises(InvalidPolicyActionError):
            ArenaRunner(self.config).run(
                self.simulator, "arena_development", [400000], 1, [InvalidActionPolicy()]
            )

    def test_arena_rejects_invalid_split_seed_combination(self) -> None:
        with self.assertRaises(InvalidSeedError):
            ArenaRunner(self.config).run(
                self.simulator, "arena_development", [900000], 1, primary_baseline_policies()
            )

    def test_records_contain_required_file_based_fields(self) -> None:
        report = ArenaRunner(self.config).run(
            self.simulator, "arena_development", [400000], 1, primary_baseline_policies()
        )
        record = report.per_seed_results["400000"]["NO_INTERVENTION"]["decisions"][0]
        required = {
            "event_id",
            "simulator_version",
            "split",
            "seed",
            "policy_name",
            "action",
            "decision_timestamp",
            "observable_context_ref",
            "outcome_status",
            "recovered_amount_paise",
            "action_cost_paise",
            "fatigue_penalty_paise",
            "net_recovery_value_paise",
        }
        self.assertTrue(required.issubset(record))


if __name__ == "__main__":
    unittest.main()
