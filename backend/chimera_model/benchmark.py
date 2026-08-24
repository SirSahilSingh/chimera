"""Gate 3.5 model candidates and compatibility adapters.

This module deliberately keeps the benchmark dependency-light.  The tree
candidate is a deterministic gradient booster over shallow decision stumps,
implemented with NumPy so the repository does not acquire a second ML runtime
or an unpinned native dependency.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from backend.chimera_simulator import Simulator
from backend.chimera_simulator.models import ACTIONS, PaymentFailureEvent

from .features import (
    FORBIDDEN_FIELD_NAMES,
    FeatureSchema,
    ObservableFeatureBuilder,
    build_feature_builder,
)
from .logistic import LogisticRegression, PlattCalibrator, sigmoid
from .model import ModelCompatibilityError


INTERACTION_FEATURE_SCHEMA_VERSION = "features_v2.0.0_interaction"
INTERACTION_MODEL_VERSION = "recovery_model_v2_interaction_lr.0.0"
TREE_MODEL_VERSION = "recovery_model_v3_gradient_boosting.0.0"

_FAILURE_REASONS = (
    "issuer_decline",
    "expired_method",
    "technical_degradation",
    "insufficient_funds",
    "abandonment",
    "other",
)
_PAYMENT_METHODS = ("card", "upi", "netbanking")
_COMMUNICATION_VALUES = ("allowed",)
_SUBSCRIPTION_VALUES = ("active",)
_PRIOR_RESPONSE_VALUES = ("none", "ignored", "read", "willing_to_pay")


def _interaction_names() -> tuple[str, ...]:
    names: list[str] = []
    for action in ACTIONS:
        prefix = f"interaction_{action}"
        names.extend(f"{prefix}_failure_reason_{value}" for value in _FAILURE_REASONS)
        names.append(f"{prefix}_incident_flag")
        names.extend(f"{prefix}_payment_method_{value}" for value in _PAYMENT_METHODS)
        names.extend(f"{prefix}_communication_preference_{value}" for value in _COMMUNICATION_VALUES)
        names.extend(f"{prefix}_subscription_state_{value}" for value in _SUBSCRIPTION_VALUES)
        names.extend(f"{prefix}_prior_response_{value}" for value in _PRIOR_RESPONSE_VALUES)
        names.append(f"{prefix}_contacts_last_7_days")
        names.append(f"{prefix}_historic_recovery_ratio")
    return tuple(names)


class InteractionFeatureBuilder:
    """Add only documented action-context interactions to the v1 observables."""

    def __init__(self, base_builder: ObservableFeatureBuilder | None = None) -> None:
        self.base_builder = base_builder or build_feature_builder()
        base = self.base_builder.schema
        self.schema = FeatureSchema(
            version=INTERACTION_FEATURE_SCHEMA_VERSION,
            feature_names=base.feature_names + _interaction_names(),
            allowed_source_fields=base.allowed_source_fields,
            forbidden_source_fields=FORBIDDEN_FIELD_NAMES,
        )

    def validate_event(self, event: PaymentFailureEvent) -> None:
        self.base_builder.validate_event(event)

    def build_mapping(self, event: PaymentFailureEvent, candidate_action: str) -> dict[str, float]:
        base_values = self.base_builder.build_mapping(event, candidate_action)
        context = event.context
        values = dict(base_values)
        for action in ACTIONS:
            active = candidate_action == action
            prefix = f"interaction_{action}"
            for value in _FAILURE_REASONS:
                values[f"{prefix}_failure_reason_{value}"] = float(active and event.failure_reason == value)
            values[f"{prefix}_incident_flag"] = float(active and context.incident_flag)
            for value in _PAYMENT_METHODS:
                values[f"{prefix}_payment_method_{value}"] = float(active and event.payment_method == value)
            for value in _COMMUNICATION_VALUES:
                values[f"{prefix}_communication_preference_{value}"] = float(
                    active and context.communication_preference == value
                )
            for value in _SUBSCRIPTION_VALUES:
                values[f"{prefix}_subscription_state_{value}"] = float(active and context.subscription_state == value)
            prior_response = context.prior_response or "none"
            for value in _PRIOR_RESPONSE_VALUES:
                values[f"{prefix}_prior_response_{value}"] = float(active and prior_response == value)
            values[f"{prefix}_contacts_last_7_days"] = float(context.contacts_last_7_days if active else 0.0)
            values[f"{prefix}_historic_recovery_ratio"] = float(
                context.historic_recovery_rate if active else 0.0
            )
        if set(values) != set(self.schema.feature_names):
            missing = set(self.schema.feature_names).difference(values)
            extra = set(values).difference(self.schema.feature_names)
            raise ModelCompatibilityError(f"interaction feature schema mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
        return {name: values[name] for name in self.schema.feature_names}

    def build_vector(self, event: PaymentFailureEvent, candidate_action: str) -> np.ndarray:
        mapping = self.build_mapping(event, candidate_action)
        return np.asarray([mapping[name] for name in self.schema.feature_names], dtype=np.float64)


@dataclass
class GradientBoostedStumps:
    """Small deterministic logistic-loss gradient booster over decision stumps."""

    learning_rate: float = 0.08
    n_estimators: int = 24
    max_thresholds_per_feature: int = 12
    l2: float = 1e-3
    random_seed: int = 0
    base_logit: float = 0.0
    stumps: list[dict[str, float | int]] | None = None

    def fit(self, features: np.ndarray, labels: np.ndarray) -> "GradientBoostedStumps":
        x = np.asarray(features, dtype=np.float64)
        y = np.asarray(labels, dtype=np.float64)
        if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0] or not x.shape[0]:
            raise ValueError("tree features and labels must have matching non-empty shapes")
        if not np.all(np.isfinite(x)) or not np.all(np.isin(y, [0.0, 1.0])):
            raise ValueError("tree features and labels must be finite binary data")
        if not (0 < self.learning_rate <= 1) or self.n_estimators <= 0 or self.max_thresholds_per_feature <= 0:
            raise ValueError("invalid gradient boosting hyperparameters")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise ValueError("random_seed must be an integer")
        positive_rate = float(np.clip(y.mean(), 1e-6, 1.0 - 1e-6))
        self.base_logit = float(np.log(positive_rate / (1.0 - positive_rate)))
        logits = np.full(x.shape[0], self.base_logit, dtype=np.float64)
        self.stumps = []
        thresholds_by_feature = [self._thresholds(x[:, index]) for index in range(x.shape[1])]
        for _ in range(self.n_estimators):
            probabilities = sigmoid(logits)
            residual = y - probabilities
            curvature = np.maximum(probabilities * (1.0 - probabilities), 1e-5)
            best: tuple[float, int, float, float, float] | None = None
            for feature_index, thresholds in enumerate(thresholds_by_feature):
                column = x[:, feature_index]
                for threshold in thresholds:
                    left = column <= threshold
                    if not left.any() or left.all():
                        continue
                    right = ~left
                    left_value = float(residual[left].sum() / (curvature[left].sum() + self.l2))
                    right_value = float(residual[right].sum() / (curvature[right].sum() + self.l2))
                    gain = float(
                        (residual[left].sum() ** 2) / (curvature[left].sum() + self.l2)
                        + (residual[right].sum() ** 2) / (curvature[right].sum() + self.l2)
                    )
                    candidate = (gain, -feature_index, -threshold, left_value, right_value)
                    if best is None or candidate[:3] > best[:3]:
                        best = candidate
            if best is None:
                break
            _, negative_feature, negative_threshold, left_value, right_value = best
            feature_index = int(-negative_feature)
            threshold = float(-negative_threshold)
            self.stumps.append(
                {
                    "feature_index": feature_index,
                    "threshold": threshold,
                    "left_value": left_value,
                    "right_value": right_value,
                }
            )
            logits += self.learning_rate * np.where(x[:, feature_index] <= threshold, left_value, right_value)
        return self

    def _thresholds(self, column: np.ndarray) -> tuple[float, ...]:
        unique = np.unique(column)
        if unique.size <= self.max_thresholds_per_feature + 1:
            return tuple(float((left + right) / 2.0) for left, right in zip(unique[:-1], unique[1:]))
        quantiles = np.linspace(0.05, 0.95, self.max_thresholds_per_feature)
        values = np.unique(np.quantile(column, quantiles))
        return tuple(float(value) for value in values if value > unique[0] and value < unique[-1])

    def predict_logit(self, features: np.ndarray) -> np.ndarray:
        if self.stumps is None:
            raise ValueError("tree model has not been fitted")
        x = np.asarray(features, dtype=np.float64)
        logits = np.full(x.shape[0], self.base_logit, dtype=np.float64)
        for stump in self.stumps:
            index = int(stump["feature_index"])
            logits += self.learning_rate * np.where(
                x[:, index] <= float(stump["threshold"]),
                float(stump["left_value"]),
                float(stump["right_value"]),
            )
        return logits

    def predict_probability(self, features: np.ndarray) -> np.ndarray:
        return sigmoid(self.predict_logit(features))


@dataclass
class BenchmarkProbabilityModel:
    """Versioned probability model with the same inference contract as Gate 3."""

    model_version: str
    simulator_version: str
    simulator_config_hash: str
    feature_schema: FeatureSchema
    classifier: Any
    calibrator: PlattCalibrator
    calibration_method: str
    training_metadata: dict[str, Any]

    def _validate_matrix(self, features: np.ndarray) -> np.ndarray:
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(self.feature_schema.feature_names):
            raise ModelCompatibilityError("feature matrix is incompatible with benchmark model schema")
        if not np.all(np.isfinite(matrix)):
            raise ModelCompatibilityError("feature matrix contains non-finite values")
        return matrix

    def base_probabilities(self, features: np.ndarray) -> np.ndarray:
        return np.clip(self.classifier.predict_probability(self._validate_matrix(features)), 0.0, 1.0)

    def calibrated_probabilities(self, features: np.ndarray) -> np.ndarray:
        matrix = self._validate_matrix(features)
        return np.clip(self.calibrator.transform(self.classifier.predict_logit(matrix)), 0.0, 1.0)

    def predict_probability(
        self,
        observable_context: PaymentFailureEvent,
        candidate_action: str,
        feature_builder: Any | None = None,
    ) -> float:
        builder = feature_builder or build_feature_builder()
        if builder.schema.to_dict() != self.feature_schema.to_dict():
            raise ModelCompatibilityError("feature builder schema is incompatible with benchmark model")
        vector = builder.build_vector(observable_context, candidate_action).reshape(1, -1)
        return float(self.calibrated_probabilities(vector)[0])

    def score_actions(self, event: PaymentFailureEvent, feature_builder: Any | None = None) -> dict[str, float]:
        builder = feature_builder or build_feature_builder()
        return {action: self.predict_probability(event, action, builder) for action in event.available_actions}

    def to_artifact_dict(self) -> dict[str, Any]:
        if isinstance(self.classifier, LogisticRegression):
            classifier: dict[str, Any] = {
                "type": "logistic_regression",
                "l2": self.classifier.l2,
                "max_iterations": self.classifier.max_iterations,
                "iterations": self.classifier.iterations,
                "intercept": self.classifier.intercept,
                "coefficients": self.classifier.coefficients.tolist() if self.classifier.coefficients is not None else None,
            }
        elif isinstance(self.classifier, GradientBoostedStumps):
            classifier = {
                "type": "gradient_boosted_stumps",
                "learning_rate": self.classifier.learning_rate,
                "n_estimators": self.classifier.n_estimators,
                "max_thresholds_per_feature": self.classifier.max_thresholds_per_feature,
                "l2": self.classifier.l2,
                "random_seed": self.classifier.random_seed,
                "base_logit": self.classifier.base_logit,
                "stumps": self.classifier.stumps,
            }
        else:
            raise ModelCompatibilityError("unsupported benchmark classifier")
        return {
            "model_version": self.model_version,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "simulator_version": self.simulator_version,
            "simulator_config_hash": self.simulator_config_hash,
            "feature_schema": self.feature_schema.to_dict(),
            "action_order": list(ACTIONS),
            "classifier": classifier,
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
    ) -> "BenchmarkProbabilityModel":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            schema_payload = payload["feature_schema"]
            schema = FeatureSchema(
                version=schema_payload["version"],
                feature_names=tuple(schema_payload["feature_names"]),
                allowed_source_fields=tuple(schema_payload["allowed_source_fields"]),
                forbidden_source_fields=tuple(schema_payload["forbidden_source_fields"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ModelCompatibilityError(f"cannot load benchmark artifact: {path}") from exc
        if expected_schema is not None and schema.to_dict() != expected_schema.to_dict():
            raise ModelCompatibilityError("benchmark feature schema is incompatible")
        if expected_simulator_version is not None and payload.get("simulator_version") != expected_simulator_version:
            raise ModelCompatibilityError("benchmark simulator version is incompatible")
        if expected_config_hash is not None and payload.get("simulator_config_hash") != expected_config_hash:
            raise ModelCompatibilityError("benchmark simulator configuration hash is incompatible")
        if tuple(payload.get("action_order", ())) != ACTIONS:
            raise ModelCompatibilityError("benchmark action order is incompatible")
        classifier_payload = payload["classifier"]
        classifier_type = classifier_payload["type"]
        if classifier_type == "logistic_regression":
            classifier = LogisticRegression(
                l2=float(classifier_payload["l2"]),
                max_iterations=int(classifier_payload["max_iterations"]),
                coefficients=np.asarray(classifier_payload["coefficients"], dtype=np.float64),
                intercept=float(classifier_payload["intercept"]),
                iterations=int(classifier_payload.get("iterations", 0)),
            )
        elif classifier_type == "gradient_boosted_stumps":
            classifier = GradientBoostedStumps(
                learning_rate=float(classifier_payload["learning_rate"]),
                n_estimators=int(classifier_payload["n_estimators"]),
                max_thresholds_per_feature=int(classifier_payload["max_thresholds_per_feature"]),
                l2=float(classifier_payload["l2"]),
                random_seed=int(classifier_payload.get("random_seed", 0)),
                base_logit=float(classifier_payload["base_logit"]),
                stumps=list(classifier_payload["stumps"]),
            )
        else:
            raise ModelCompatibilityError(f"unsupported benchmark classifier type: {classifier_type}")
        calibration = payload["calibration"]
        return cls(
            model_version=str(payload["model_version"]),
            simulator_version=str(payload["simulator_version"]),
            simulator_config_hash=str(payload["simulator_config_hash"]),
            feature_schema=schema,
            classifier=classifier,
            calibrator=PlattCalibrator(
                a=float(calibration["a"]),
                b=float(calibration["b"]),
                iterations=int(calibration.get("iterations", 0)),
            ),
            calibration_method=str(calibration["method"]),
            training_metadata=dict(payload.get("training_metadata", {})),
        )


def train_benchmark_model(
    model_version: str,
    train_dataset: Any,
    validation_dataset: Any,
    simulator: Simulator,
    feature_schema: FeatureSchema,
    training_metadata: Mapping[str, Any],
    *,
    classifier: str,
) -> BenchmarkProbabilityModel:
    if train_dataset.split != "training" or validation_dataset.split != "validation":
        raise ModelCompatibilityError("benchmark training requires training data and validation calibration data")
    if train_dataset.feature_names != feature_schema.feature_names or validation_dataset.feature_names != feature_schema.feature_names:
        raise ModelCompatibilityError("benchmark datasets do not match feature schema")
    if classifier == "interaction_logistic_regression":
        fitted = LogisticRegression(l2=1e-4, max_iterations=80).fit(train_dataset.features, train_dataset.labels)
    elif classifier == "gradient_boosted_stumps":
        fitted = GradientBoostedStumps(learning_rate=0.08, n_estimators=24, max_thresholds_per_feature=12, l2=1e-3, random_seed=0).fit(
            train_dataset.features, train_dataset.labels
        )
    else:
        raise ValueError(f"unknown benchmark classifier: {classifier}")
    calibrator = PlattCalibrator().fit(
        fitted.predict_logit(validation_dataset.features), validation_dataset.labels
    )
    return BenchmarkProbabilityModel(
        model_version=model_version,
        simulator_version=simulator.config.simulator_version,
        simulator_config_hash=simulator.config.config_hash,
        feature_schema=feature_schema,
        classifier=fitted,
        calibrator=calibrator,
        calibration_method="platt_scaling_on_validation_split",
        training_metadata=dict(training_metadata),
    )


class Gate4ModelAdapter:
    """Expose a selected benchmark model through the unchanged Gate 4 contract.

    Gate 4 still receives the original v1 schema builder and compatibility
    identifiers.  Prediction is delegated to the selected model's own
    observable-only builder; the underlying artifact version remains auditable.
    """

    def __init__(self, selected_model: BenchmarkProbabilityModel, gate4_schema: FeatureSchema, gate4_model_version: str) -> None:
        self.selected_model = selected_model
        self.model_version = gate4_model_version
        self.simulator_version = selected_model.simulator_version
        self.simulator_config_hash = selected_model.simulator_config_hash
        self.feature_schema = gate4_schema
        self._selected_builder = (
            InteractionFeatureBuilder() if selected_model.feature_schema.version == INTERACTION_FEATURE_SCHEMA_VERSION else build_feature_builder()
        )

    def predict_probability(self, observable_context: PaymentFailureEvent, candidate_action: str, feature_builder: Any | None = None) -> float:
        return self.selected_model.predict_probability(observable_context, candidate_action, self._selected_builder)

    def score_actions(self, event: PaymentFailureEvent, feature_builder: Any | None = None) -> dict[str, float]:
        return {action: self.predict_probability(event, action, feature_builder) for action in event.available_actions}
