from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import numpy as np

from backend.chimera_model import (
    DatasetSpec,
    FeatureSchemaError,
    ForbiddenFeatureError,
    ModelCompatibilityError,
    RecoveryProbabilityModel,
    TemporalLeakageError,
    build_feature_builder,
    generate_dataset,
    generate_experiment_datasets,
)
from backend.chimera_model.dataset import DatasetError
from backend.chimera_model.logistic import PlattCalibrator
from backend.chimera_simulator import ACTIONS, Simulator, SimulatorConfig
from backend.chimera_simulator.models import CONTACT_ACTIONS, HistoricalPayment
from backend.chimera_simulator.seeds import InvalidSeedError


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend" / "configs" / "simulator_v1.yaml"


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig.from_file(CONFIG_PATH)
        cls.simulator = Simulator(cls.config)
        cls.builder = build_feature_builder()

    def _small_datasets(self):
        train = generate_dataset(
            self.simulator,
            DatasetSpec("training", (100000, 110000), 10),
            self.builder,
        )
        validation = generate_dataset(
            self.simulator,
            DatasetSpec("validation", (200000,), 10),
            self.builder,
        )
        holdout = generate_dataset(
            self.simulator,
            DatasetSpec("holdout", (300000,), 10),
            self.builder,
        )
        return train, validation, holdout

    def _small_model(self) -> RecoveryProbabilityModel:
        train, validation, _ = self._small_datasets()
        return RecoveryProbabilityModel.train(
            train,
            validation,
            self.simulator,
            self.builder.schema,
            {"test": True},
        )

    def test_forbidden_simulator_truth_record_is_rejected(self) -> None:
        case = self.simulator.generate_case("training", 100000, 0)
        with self.assertRaises(FeatureSchemaError):
            self.builder.build_vector(case, "RETRY_NOW")

    def test_hidden_field_injected_into_event_is_rejected(self) -> None:
        event = self.simulator.generate_case("training", 100000, 0).event
        object.__setattr__(event, "hidden_state", "forbidden")
        with self.assertRaises(ForbiddenFeatureError):
            self.builder.build_vector(event, "RETRY_NOW")

    def test_future_observable_record_is_rejected(self) -> None:
        event = self.simulator.generate_case("training", 100000, 1).event
        future = HistoricalPayment(
            "future-payment",
            event.decision_timestamp + timedelta(seconds=1),
            100,
            "succeeded",
            "synthetic",
        )
        future_context = replace(
            event.context,
            historical_payments=event.context.historical_payments + (future,),
        )
        future_event = replace(event, context=future_context)
        with self.assertRaises(TemporalLeakageError):
            self.builder.build_vector(future_event, "RETRY_NOW")

    def test_model_dataset_rejects_arena_splits_and_invalid_seed_ranges(self) -> None:
        with self.assertRaises(DatasetError):
            DatasetSpec("arena_development", (400000,), 1)
        with self.assertRaises(InvalidSeedError):
            generate_dataset(
                self.simulator,
                DatasetSpec("training", (400000,), 1),
                self.builder,
            )

    def test_event_level_split_isolation_and_action_row_grouping(self) -> None:
        datasets = generate_experiment_datasets(
            self.simulator,
            {
                "training": DatasetSpec("training", (100000,), 12),
                "validation": DatasetSpec("validation", (200000,), 12),
                "holdout": DatasetSpec("holdout", (300000,), 12),
            },
            self.builder,
        )
        event_ids = {split: set(dataset.event_ids) for split, dataset in datasets.items()}
        self.assertEqual(len(event_ids["training"]), 12)
        self.assertEqual(len(event_ids["validation"]), 12)
        self.assertEqual(len(event_ids["holdout"]), 12)
        for left in event_ids:
            for right in event_ids:
                if left < right:
                    self.assertEqual(event_ids[left].intersection(event_ids[right]), set())

        for split, dataset in datasets.items():
            self.assertEqual(set(dataset.row_event_ids), event_ids[split])
            for event_id in dataset.event_ids:
                self.assertEqual(dataset.row_event_ids.count(event_id), len(ACTIONS))
            self.assertTrue(all(event_id.split(":")[1] == split for event_id in dataset.row_event_ids))

    def test_action_dependent_features_have_explicit_contact_semantics(self) -> None:
        # At event index 500, the synthetic decision hour is 20:20, outside 08:00-19:00.
        event = self.simulator.generate_case("training", 100000, 500).event
        names = self.builder.schema.feature_names
        rows = {
            action: dict(zip(names, self.builder.build_vector(event, action)))
            for action in ACTIONS
        }
        action_feature_names = [name for name in names if name.startswith("candidate_action_")]
        for action, row in rows.items():
            self.assertEqual(sum(row[name] for name in action_feature_names if name.startswith("candidate_action_") and name not in {
                "candidate_action_is_outbound", "candidate_action_contact_window_eligible"
            }), 1.0)
            self.assertEqual(row[f"candidate_action_{action}"], 1.0)

        contact_actions = set(CONTACT_ACTIONS).intersection(ACTIONS)
        for action in ACTIONS:
            outbound = rows[action]["candidate_action_is_outbound"]
            eligible = rows[action]["candidate_action_contact_window_eligible"]
            if action in contact_actions:
                self.assertEqual(outbound, 1.0)
                self.assertEqual(eligible, 0.0)
            else:
                # Non-contact actions are not blocked by the contact window. The outbound flag
                # disambiguates this from an outbound action that is inside the window.
                self.assertEqual(outbound, 0.0)
                self.assertEqual(eligible, 1.0)

        self.assertNotEqual(rows["RETRY_NOW"], rows["RETRY_LATER"])
        self.assertNotEqual(rows["RETRY_NOW"]["candidate_action_RETRY_NOW"], rows["RETRY_NOW"]["candidate_action_RETRY_LATER"])

    def test_candidate_action_encoding_is_explicit(self) -> None:
        event = self.simulator.generate_case("training", 100000, 2).event
        retry = self.builder.build_vector(event, "RETRY_NOW")
        later = self.builder.build_vector(event, "RETRY_LATER")
        retry_index = self.builder.schema.feature_names.index("candidate_action_RETRY_NOW")
        later_index = self.builder.schema.feature_names.index("candidate_action_RETRY_LATER")
        self.assertEqual(retry[retry_index], 1.0)
        self.assertEqual(retry[later_index], 0.0)
        self.assertEqual(later[retry_index], 0.0)
        self.assertEqual(later[later_index], 1.0)
        self.assertFalse(np.array_equal(retry, later))

    def test_training_is_deterministic(self) -> None:
        first = self._small_model()
        second = self._small_model()
        np.testing.assert_allclose(first.classifier.coefficients, second.classifier.coefficients)
        self.assertEqual(first.classifier.intercept, second.classifier.intercept)
        self.assertEqual(first.calibrator.a, second.calibrator.a)
        self.assertEqual(first.calibrator.b, second.calibrator.b)

    def test_inference_probability_bounds_and_all_action_scoring(self) -> None:
        model = self._small_model()
        event = self.simulator.generate_case("holdout", 300000, 0).event
        probabilities = model.score_actions(event, self.builder)
        self.assertEqual(set(probabilities), set(event.available_actions))
        for action, probability in probabilities.items():
            self.assertGreaterEqual(probability, 0.0, action)
            self.assertLessEqual(probability, 1.0, action)

    def test_artifact_round_trip_and_compatibility_checks(self) -> None:
        model = self._small_model()
        event = self.simulator.generate_case("holdout", 300000, 0).event
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            model.save(path)
            loaded = RecoveryProbabilityModel.load(
                path,
                expected_simulator_version=self.config.simulator_version,
                expected_config_hash=self.config.config_hash,
                expected_schema=self.builder.schema,
            )
            self.assertEqual(model.score_actions(event, self.builder), loaded.score_actions(event, self.builder))

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["simulator_version"] = "simulator_v9.0.0"
            incompatible_version = Path(directory) / "incompatible-version.json"
            incompatible_version.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ModelCompatibilityError):
                RecoveryProbabilityModel.load(
                    incompatible_version,
                    expected_simulator_version=self.config.simulator_version,
                )

            payload["simulator_version"] = self.config.simulator_version
            payload["feature_schema"]["version"] = "features_v9.0.0"
            incompatible_schema = Path(directory) / "incompatible-schema.json"
            incompatible_schema.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ModelCompatibilityError):
                RecoveryProbabilityModel.load(incompatible_schema, expected_schema=self.builder.schema)

    def test_calibration_pipeline_returns_bounded_probabilities(self) -> None:
        logits = np.asarray([-3.0, -1.0, 0.0, 1.0, 3.0, 4.0])
        labels = np.asarray([0, 0, 0, 1, 1, 1], dtype=np.float64)
        calibrator = PlattCalibrator().fit(logits, labels)
        probabilities = calibrator.transform(logits)
        self.assertTrue(np.all(probabilities >= 0.0))
        self.assertTrue(np.all(probabilities <= 1.0))
        self.assertTrue(np.all(np.diff(probabilities) >= 0.0))


if __name__ == "__main__":
    unittest.main()
