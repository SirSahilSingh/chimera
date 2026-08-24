"""Train and evaluate the Gate 3 synthetic recovery-probability model."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.chimera_model import DatasetSpec, RecoveryProbabilityModel, build_feature_builder, generate_experiment_datasets
from backend.chimera_model.metrics import summarize_predictions
from backend.chimera_simulator import ACTIONS, Simulator


DEFAULT_TRAINING_SEEDS = tuple(range(100000, 200000, 10000))
DEFAULT_VALIDATION_SEEDS = (200000, 210000, 220000)
DEFAULT_HOLDOUT_SEEDS = (300000, 310000, 320000)


def _evaluate_dataset(dataset, base_probabilities: np.ndarray, calibrated_probabilities: np.ndarray) -> dict[str, Any]:
    per_action: dict[str, Any] = {}
    for action in ACTIONS:
        mask = np.asarray([row_action == action for row_action in dataset.row_actions], dtype=bool)
        if int(mask.sum()) >= 100:
            per_action[action] = summarize_predictions(dataset.labels[mask], calibrated_probabilities[mask])
        else:
            per_action[action] = {
                "row_count": int(mask.sum()),
                "insufficient_sample": True,
            }
    return {
        "overall": summarize_predictions(dataset.labels, calibrated_probabilities),
        "base_uncalibrated": summarize_predictions(dataset.labels, base_probabilities),
        "per_action_calibrated": per_action,
    }


def _calibration_comparison(dataset, base_probabilities, calibrated_probabilities) -> dict[str, Any]:
    before = summarize_predictions(dataset.labels, base_probabilities)
    after = summarize_predictions(dataset.labels, calibrated_probabilities)
    return {
        "split": dataset.split,
        "before": {
            "brier_score": before["brier_score"],
            "calibration_curve": before["calibration_curve"],
        },
        "after": {
            "brier_score": after["brier_score"],
            "calibration_curve": after["calibration_curve"],
        },
    }


def run_experiment(config_path: Path, output_dir: Path, events_per_seed: int) -> dict[str, Any]:
    simulator = Simulator(config_path)
    feature_builder = build_feature_builder()
    specs = {
        "training": DatasetSpec("training", DEFAULT_TRAINING_SEEDS, events_per_seed),
        "validation": DatasetSpec("validation", DEFAULT_VALIDATION_SEEDS, events_per_seed),
        "holdout": DatasetSpec("holdout", DEFAULT_HOLDOUT_SEEDS, events_per_seed),
    }
    datasets = generate_experiment_datasets(simulator, specs, feature_builder)
    training_timestamp = datetime.now(timezone.utc).isoformat()
    training_metadata = {
        "experiment_version": "gate3_experiment_v1.0.0",
        "training_timestamp_utc": training_timestamp,
        "dataset_specs": {split: spec.to_dict() for split, spec in specs.items()},
        "event_counts": {split: dataset.event_count for split, dataset in datasets.items()},
        "row_counts": {split: dataset.row_count for split, dataset in datasets.items()},
        "model_hyperparameters": {"type": "logistic_regression", "l2": 1e-4, "max_iterations": 80},
        "calibration_method": "Platt scaling fitted only on validation split",
    }
    model = RecoveryProbabilityModel.train(
        datasets["training"],
        datasets["validation"],
        simulator,
        feature_builder.schema,
        training_metadata,
    )

    predictions: dict[str, dict[str, np.ndarray]] = {}
    for split, dataset in datasets.items():
        base = model.base_probabilities(dataset.features)
        calibrated = model.calibrated_probabilities(dataset.features)
        predictions[split] = {"base": base, "calibrated": calibrated}

    report = {
        "model_version": model.model_version,
        "simulator_version": simulator.config.simulator_version,
        "simulator_config_hash": simulator.config.config_hash,
        "feature_schema": feature_builder.schema.to_dict(),
        "training_metadata": training_metadata,
        "datasets": {split: dataset.manifest() for split, dataset in datasets.items()},
        "metrics": {
            split: _evaluate_dataset(dataset, predictions[split]["base"], predictions[split]["calibrated"])
            for split, dataset in datasets.items()
        },
        "calibration": _calibration_comparison(
            datasets["validation"], predictions["validation"]["base"], predictions["validation"]["calibrated"]
        ),
        "holdout_evaluation_policy": "holdout is evaluated after training and validation calibration; no holdout tuning",
    }

    example_case = simulator.generate_case("holdout", DEFAULT_HOLDOUT_SEEDS[0], 0)
    report["example_event"] = {
        "event_id": example_case.event.event_id,
        "observable_failure_reason": example_case.event.failure_reason,
        "observable_incident_flag": example_case.event.context.incident_flag,
        "amount_paise": example_case.event.amount_paise,
        "predicted_probability_by_action": model.score_actions(example_case.event, feature_builder),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    model.save(output_dir / "recovery_model_v1.json")
    (output_dir / "feature_schema.json").write_text(
        json.dumps(feature_builder.schema.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "dataset_manifest.json").write_text(
        json.dumps(report["datasets"], indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "backend" / "configs" / "simulator_v1.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "model_v1")
    parser.add_argument("--events-per-seed", type=int, default=500)
    args = parser.parse_args()
    report = run_experiment(args.config, args.output_dir, args.events_per_seed)
    print(json.dumps({
        "model_version": report["model_version"],
        "simulator_config_hash": report["simulator_config_hash"],
        "datasets": report["datasets"],
        "holdout": report["metrics"]["holdout"]["overall"],
        "calibration": report["calibration"],
        "output_dir": str(args.output_dir),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
