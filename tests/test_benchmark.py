from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import numpy as np

from backend.chimera_engine import DecisionEngine
from backend.chimera_model import (
    DatasetSpec,
    BenchmarkProbabilityModel,
    ForbiddenFeatureError,
    Gate4ModelAdapter,
    InteractionFeatureBuilder,
    ModelCompatibilityError,
    TemporalLeakageError,
    build_feature_builder,
    generate_dataset,
    generate_experiment_datasets,
    train_benchmark_model,
)
from backend.chimera_model.benchmark import INTERACTION_MODEL_VERSION
from backend.chimera_simulator import ACTIONS, Simulator, SimulatorConfig
from backend.chimera_simulator.models import HistoricalPayment
from backend.chimera_simulator.seeds import InvalidSeedError


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend" / "configs" / "simulator_v1.yaml"
V1_ARTIFACT = ROOT / "data" / "model_v1" / "recovery_model_v1.json"
V1_ARTIFACT_SHA256 = "a6a8de47d3bad06141ea5d418b6250bc8bd084ca9ee424e0bf74b6396ec2bdb4"


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig.from_file(CONFIG_PATH)
        cls.simulator = Simulator(cls.config)
        cls.base_builder = build_feature_builder()
        cls.interaction_builder = InteractionFeatureBuilder()

    def _datasets(self):
        specs = {
            "training": DatasetSpec("training", (100000,), 12),
            "validation": DatasetSpec("validation", (200000,), 12),
            "holdout": DatasetSpec("holdout", (300000,), 12),
        }
        return generate_experiment_datasets(self.simulator, specs, self.interaction_builder)

    def _model(self, classifier: str = "interaction_logistic_regression"):
        datasets = self._datasets()
        return train_benchmark_model(
            INTERACTION_MODEL_VERSION if classifier.startswith("interaction") else "recovery_model_v3_gradient_boosting.0.0",
            datasets["training"],
            datasets["validation"],
            self.simulator,
            self.interaction_builder.schema,
            {
                "seed_policy": {"training": [100000, 199999], "validation": [200000, 299999], "holdout": [300000, 399999]},
                "protocol": "fit training; calibrate validation; holdout untouched",
            },
            classifier=classifier,
        )

    def test_interaction_schema_and_action_context_fields_are_explicit(self) -> None:
        event = self.simulator.generate_case("validation", 200000, 0).event
        retry = self.interaction_builder.build_mapping(event, "RETRY_NOW")
        later = self.interaction_builder.build_mapping(event, "RETRY_LATER")
        self.assertIn("interaction_RETRY_NOW_failure_reason_" + event.failure_reason, retry)
        self.assertEqual(retry["interaction_RETRY_NOW_failure_reason_" + event.failure_reason], 1.0)
        self.assertEqual(retry["interaction_RETRY_LATER_failure_reason_" + event.failure_reason], 0.0)
        self.assertEqual(later["interaction_RETRY_NOW_failure_reason_" + event.failure_reason], 0.0)
        self.assertEqual(later["interaction_RETRY_LATER_failure_reason_" + event.failure_reason], 1.0)
        self.assertEqual(len(self.interaction_builder.schema.feature_names), 170)

    def test_all_benchmark_feature_builders_reject_hidden_and_future_information(self) -> None:
        event = self.simulator.generate_case("validation", 200000, 1).event
        object.__setattr__(event, "customer_segment", "HIDDEN")
        with self.assertRaises(ForbiddenFeatureError):
            self.interaction_builder.build_vector(event, "RETRY_NOW")

        clean_event = self.simulator.generate_case("validation", 200000, 2).event
        future = HistoricalPayment(
            "future",
            clean_event.decision_timestamp + timedelta(seconds=1),
            100,
            "succeeded",
            "synthetic",
        )
        future_event = replace(clean_event, context=replace(clean_event.context, historical_payments=(future,)))
        with self.assertRaises(TemporalLeakageError):
            self.interaction_builder.build_vector(future_event, "RETRY_NOW")

    def test_event_level_split_isolation_and_action_rows(self) -> None:
        datasets = self._datasets()
        ids = {split: set(dataset.event_ids) for split, dataset in datasets.items()}
        self.assertEqual({split: len(values) for split, values in ids.items()}, {"training": 12, "validation": 12, "holdout": 12})
        self.assertEqual(len(ids["training"] & ids["validation"]), 0)
        self.assertEqual(len(ids["training"] & ids["holdout"]), 0)
        self.assertEqual(len(ids["validation"] & ids["holdout"]), 0)
        for dataset in datasets.values():
            for event_id in dataset.event_ids:
                self.assertEqual(dataset.row_event_ids.count(event_id), len(ACTIONS))

    def test_arena_seeds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DatasetSpec("arena_development", (400000,), 1)
        with self.assertRaises(InvalidSeedError):
            generate_dataset(self.simulator, DatasetSpec("training", (400000,), 1), self.interaction_builder)

    def test_training_protocol_requires_training_and_validation(self) -> None:
        datasets = self._datasets()
        with self.assertRaises(ModelCompatibilityError):
            train_benchmark_model(
                INTERACTION_MODEL_VERSION,
                datasets["validation"],
                datasets["holdout"],
                self.simulator,
                self.interaction_builder.schema,
                {},
                classifier="interaction_logistic_regression",
            )

    def test_classifier_fit_uses_training_only_and_calibration_uses_validation(self) -> None:
        datasets = self._datasets()
        metadata = {"protocol": "fit training; calibrate validation; holdout untouched"}
        first = train_benchmark_model(
            INTERACTION_MODEL_VERSION,
            datasets["training"],
            datasets["validation"],
            self.simulator,
            self.interaction_builder.schema,
            metadata,
            classifier="interaction_logistic_regression",
        )
        altered_validation = replace(datasets["validation"], labels=1.0 - datasets["validation"].labels)
        second = train_benchmark_model(
            INTERACTION_MODEL_VERSION,
            datasets["training"],
            altered_validation,
            self.simulator,
            self.interaction_builder.schema,
            metadata,
            classifier="interaction_logistic_regression",
        )
        np.testing.assert_allclose(first.classifier.coefficients, second.classifier.coefficients)
        self.assertEqual(first.classifier.intercept, second.classifier.intercept)
        self.assertNotEqual((first.calibrator.a, first.calibrator.b), (second.calibrator.a, second.calibrator.b))

    def test_models_are_deterministic_and_holdout_prediction_does_not_mutate_parameters(self) -> None:
        first = self._model("gradient_boosted_stumps")
        second = self._model("gradient_boosted_stumps")
        self.assertEqual(first.classifier.stumps, second.classifier.stumps)
        self.assertEqual(first.classifier.base_logit, second.classifier.base_logit)
        datasets = self._datasets()
        before = [dict(stump) for stump in first.classifier.stumps]
        first.calibrated_probabilities(datasets["holdout"].features)
        self.assertEqual(before, first.classifier.stumps)

    def test_benchmark_artifact_round_trip_and_compatibility(self) -> None:
        model = self._model()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "interaction.json"
            model.save(path)
            loaded = type(model).load(
                path,
                expected_simulator_version=self.config.simulator_version,
                expected_config_hash=self.config.config_hash,
                expected_schema=self.interaction_builder.schema,
            )
            event = self.simulator.generate_case("holdout", 300000, 0).event
            self.assertEqual(
                model.score_actions(event, self.interaction_builder),
                loaded.score_actions(event, self.interaction_builder),
            )
            with self.assertRaises(ModelCompatibilityError):
                type(model).load(path, expected_simulator_version="simulator_v9.0.0")
            with self.assertRaises(ModelCompatibilityError):
                type(model).load(path, expected_schema=self.base_builder.schema)

    def test_gate4_adapter_uses_selected_model_without_engine_changes(self) -> None:
        model = self._model()
        adapter = Gate4ModelAdapter(model, self.base_builder.schema, "recovery_model_v1.0.0")
        engine = DecisionEngine(adapter, self.config)
        event = self.simulator.generate_case("holdout", 300000, 0).event
        decision = engine.decide(event)
        self.assertIn(decision.selected_action, ACTIONS)
        self.assertEqual(adapter.selected_model.model_version, INTERACTION_MODEL_VERSION)

    def test_selected_artifact_is_gate4_compatible_through_adapter(self) -> None:
        artifact = ROOT / "data" / "model_benchmark_v1" / "recovery_model_v2_interaction_lr.json"
        selected = BenchmarkProbabilityModel.load(
            artifact,
            expected_simulator_version=self.config.simulator_version,
            expected_config_hash=self.config.config_hash,
            expected_schema=self.interaction_builder.schema,
        )
        adapter = Gate4ModelAdapter(selected, self.base_builder.schema, "recovery_model_v1.0.0")
        decision = DecisionEngine(adapter, self.config).decide(
            self.simulator.generate_case("holdout", 300000, 0).event
        )
        self.assertIn(decision.selected_action, ACTIONS)

    def test_preserved_v1_artifact_is_unchanged(self) -> None:
        digest = hashlib.sha256(V1_ARTIFACT.read_bytes()).hexdigest()
        self.assertEqual(digest, V1_ARTIFACT_SHA256)


if __name__ == "__main__":
    unittest.main()
