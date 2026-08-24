"""Action-conditioned calibrated Logistic Regression model and artifact IO."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from backend.chimera_simulator import Simulator
from backend.chimera_simulator.models import ACTIONS, PaymentFailureEvent

from .dataset import ModelDataset
from .features import FeatureSchema, ObservableFeatureBuilder
from .logistic import LogisticRegression, PlattCalibrator


MODEL_VERSION = "recovery_model_v1.0.0"


class ModelCompatibilityError(ValueError):
    """Raised when an artifact does not match the active simulator or schema."""


@dataclass
class RecoveryProbabilityModel:
    model_version: str
    simulator_version: str
    simulator_config_hash: str
    feature_schema: FeatureSchema
    classifier: LogisticRegression
    calibrator: PlattCalibrator
    calibration_method: str
    training_metadata: dict[str, Any]

    @classmethod
    def train(
        cls,
        train_dataset: ModelDataset,
        calibration_dataset: ModelDataset,
        simulator: Simulator,
        feature_schema: FeatureSchema,
        training_metadata: Mapping[str, Any],
        l2: float = 1e-4,
        max_iterations: int = 80,
    ) -> "RecoveryProbabilityModel":
        cls._validate_dataset(train_dataset, feature_schema, "training")
        cls._validate_dataset(calibration_dataset, feature_schema, "calibration")
        classifier = LogisticRegression(l2=l2, max_iterations=max_iterations).fit(
            train_dataset.features, train_dataset.labels
        )
        calibrator = PlattCalibrator().fit(
            classifier.predict_logit(calibration_dataset.features), calibration_dataset.labels
        )
        return cls(
            model_version=MODEL_VERSION,
            simulator_version=simulator.config.simulator_version,
            simulator_config_hash=simulator.config.config_hash,
            feature_schema=feature_schema,
            classifier=classifier,
            calibrator=calibrator,
            calibration_method="platt_scaling_on_validation_split",
            training_metadata=dict(training_metadata),
        )

    @staticmethod
    def _validate_dataset(dataset: ModelDataset, schema: FeatureSchema, label: str) -> None:
        if dataset.feature_names != schema.feature_names:
            raise ModelCompatibilityError(f"{label} dataset feature schema does not match model schema")
        if dataset.split not in {"training", "validation", "holdout"}:
            raise ModelCompatibilityError(f"{label} dataset uses a non-model split: {dataset.split}")

    def base_probabilities(self, features: np.ndarray) -> np.ndarray:
        self._validate_feature_matrix(features)
        return self.classifier.predict_probability(features)

    def calibrated_probabilities(self, features: np.ndarray) -> np.ndarray:
        self._validate_feature_matrix(features)
        logits = self.classifier.predict_logit(features)
        return self.calibrator.transform(logits)

    def _validate_feature_matrix(self, features: np.ndarray) -> None:
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(self.feature_schema.feature_names):
            raise ModelCompatibilityError("feature matrix is incompatible with the model feature schema")
        if not np.all(np.isfinite(matrix)):
            raise ModelCompatibilityError("feature matrix contains non-finite values")

    def predict_probability(
        self,
        observable_context: PaymentFailureEvent,
        candidate_action: str,
        feature_builder: ObservableFeatureBuilder | None = None,
    ) -> float:
        builder = feature_builder or ObservableFeatureBuilder(self.feature_schema)
        if builder.schema.to_dict() != self.feature_schema.to_dict():
            raise ModelCompatibilityError("feature builder schema is incompatible with the model")
        vector = builder.build_vector(observable_context, candidate_action).reshape(1, -1)
        return float(np.clip(self.calibrated_probabilities(vector)[0], 0.0, 1.0))

    def score_actions(
        self,
        event: PaymentFailureEvent,
        feature_builder: ObservableFeatureBuilder | None = None,
    ) -> dict[str, float]:
        builder = feature_builder or ObservableFeatureBuilder(self.feature_schema)
        return {
            action: self.predict_probability(event, action, builder)
            for action in event.available_actions
        }

    def to_artifact_dict(self) -> dict[str, Any]:
        if self.classifier.coefficients is None:
            raise ModelCompatibilityError("cannot serialize an unfitted classifier")
        return {
            "model_version": self.model_version,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "simulator_version": self.simulator_version,
            "simulator_config_hash": self.simulator_config_hash,
            "feature_schema": self.feature_schema.to_dict(),
            "action_order": list(ACTIONS),
            "classifier": {
                "type": "logistic_regression",
                "l2": self.classifier.l2,
                "max_iterations": self.classifier.max_iterations,
                "iterations": self.classifier.iterations,
                "intercept": self.classifier.intercept,
                "coefficients": self.classifier.coefficients.tolist(),
            },
            "calibration": {
                "method": self.calibration_method,
                "a": self.calibrator.a,
                "b": self.calibrator.b,
                "iterations": self.calibrator.iterations,
            },
            "training_metadata": self.training_metadata,
        }

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_artifact_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        expected_simulator_version: str | None = None,
        expected_config_hash: str | None = None,
        expected_schema: FeatureSchema | None = None,
    ) -> "RecoveryProbabilityModel":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelCompatibilityError(f"cannot load model artifact: {path}") from exc
        schema_payload = payload.get("feature_schema")
        if not isinstance(schema_payload, dict):
            raise ModelCompatibilityError("model artifact has no feature schema")
        schema = FeatureSchema(
            version=schema_payload["version"],
            feature_names=tuple(schema_payload["feature_names"]),
            allowed_source_fields=tuple(schema_payload["allowed_source_fields"]),
            forbidden_source_fields=tuple(schema_payload["forbidden_source_fields"]),
        )
        if expected_schema is not None and schema.to_dict() != expected_schema.to_dict():
            raise ModelCompatibilityError("model feature schema is incompatible with expected schema")
        if expected_simulator_version is not None and payload.get("simulator_version") != expected_simulator_version:
            raise ModelCompatibilityError("model simulator version is incompatible")
        if expected_config_hash is not None and payload.get("simulator_config_hash") != expected_config_hash:
            raise ModelCompatibilityError("model simulator configuration hash is incompatible")
        if tuple(payload.get("action_order", ())) != ACTIONS:
            raise ModelCompatibilityError("model action order is incompatible")
        classifier_payload = payload.get("classifier", {})
        calibration_payload = payload.get("calibration", {})
        classifier = LogisticRegression(
            l2=float(classifier_payload["l2"]),
            max_iterations=int(classifier_payload["max_iterations"]),
            coefficients=np.asarray(classifier_payload["coefficients"], dtype=np.float64),
            intercept=float(classifier_payload["intercept"]),
            iterations=int(classifier_payload.get("iterations", 0)),
        )
        calibrator = PlattCalibrator(
            a=float(calibration_payload["a"]),
            b=float(calibration_payload["b"]),
            iterations=int(calibration_payload.get("iterations", 0)),
        )
        return cls(
            model_version=str(payload["model_version"]),
            simulator_version=str(payload["simulator_version"]),
            simulator_config_hash=str(payload["simulator_config_hash"]),
            feature_schema=schema,
            classifier=classifier,
            calibrator=calibrator,
            calibration_method=str(calibration_payload["method"]),
            training_metadata=dict(payload.get("training_metadata", {})),
        )
