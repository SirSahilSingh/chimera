"""Run the Gate 3.5 model benchmark without Arena evaluation."""

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

from backend.chimera_model import (  # noqa: E402
    DatasetSpec,
    INTERACTION_MODEL_VERSION,
    InteractionFeatureBuilder,
    RecoveryProbabilityModel,
    TREE_MODEL_VERSION,
    build_feature_builder,
    generate_experiment_datasets,
    train_benchmark_model,
)
from backend.chimera_model.benchmark import BenchmarkProbabilityModel  # noqa: E402
from backend.chimera_model.metrics import summarize_predictions  # noqa: E402
from backend.chimera_simulator import ACTIONS, Simulator, SimulatorConfig  # noqa: E402


TRAINING_SEEDS = tuple(range(100000, 200000, 10000))
VALIDATION_SEEDS = (200000, 210000, 220000)
HOLDOUT_SEEDS = (300000, 310000, 320000)
SPLIT_SEEDS = {
    "training": TRAINING_SEEDS,
    "validation": VALIDATION_SEEDS,
    "holdout": HOLDOUT_SEEDS,
}


def _evaluate(model: Any, datasets: dict[str, Any], builder: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split, dataset in datasets.items():
        base = model.base_probabilities(dataset.features)
        calibrated = model.calibrated_probabilities(dataset.features)
        per_action: dict[str, Any] = {}
        for action in ACTIONS:
            mask = np.asarray([value == action for value in dataset.row_actions], dtype=bool)
            per_action[action] = summarize_predictions(dataset.labels[mask], calibrated[mask])
        result[split] = {
            "overall": summarize_predictions(dataset.labels, calibrated),
            "base_uncalibrated": summarize_predictions(dataset.labels, base),
            "per_action_calibrated": per_action,
            "calibration": {
                "before": {
                    "brier_score": summarize_predictions(dataset.labels, base)["brier_score"],
                    "calibration_curve": summarize_predictions(dataset.labels, base)["calibration_curve"],
                },
                "after": {
                    "brier_score": summarize_predictions(dataset.labels, calibrated)["brier_score"],
                    "calibration_curve": summarize_predictions(dataset.labels, calibrated)["calibration_curve"],
                },
            },
        }
    return result


def _dataset_manifest(datasets: dict[str, Any]) -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    for split, dataset in datasets.items():
        manifest[split] = dataset.manifest()
        manifest[split]["unique_event_ids"] = len(set(dataset.event_ids))
    overlaps: dict[str, int] = {}
    names = tuple(datasets)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlaps[f"{left}_intersection_{right}"] = len(
                set(datasets[left].event_ids).intersection(datasets[right].event_ids)
            )
    return {"splits": manifest, "event_id_overlap_counts": overlaps}


def _scenario_cases(simulator: Simulator) -> dict[str, Any]:
    cases = [simulator.generate_case("validation", VALIDATION_SEEDS[0], index) for index in range(500)]

    def first(predicate):
        return next((case for case in cases if predicate(case.event)), cases[0])

    expired = first(lambda event: event.failure_reason == "expired_method")
    technical = first(lambda event: event.failure_reason == "technical_degradation" and event.context.incident_flag)
    insufficient = max(
        (case for case in cases if case.event.failure_reason == "insufficient_funds"),
        key=lambda case: case.event.context.historic_recovery_rate,
        default=cases[0],
    )
    low_engagement = min(cases, key=lambda case: (case.event.context.historic_recovery_rate, -case.event.context.contacts_last_7_days))
    high_fatigue = max(cases, key=lambda case: case.event.context.contacts_last_7_days)
    return {
        "expired_payment_method": expired,
        "technical_degradation_incident": technical,
        "insufficient_funds_high_historical_recovery": insufficient,
        "low_engagement_observable_profile": low_engagement,
        "high_recent_contact_fatigue": high_fatigue,
    }


def _sensitivity(models: dict[str, tuple[Any, Any]], simulator: Simulator) -> dict[str, Any]:
    scenarios = _scenario_cases(simulator)
    output: dict[str, Any] = {}
    for scenario_name, case in scenarios.items():
        event = case.event
        output[scenario_name] = {
            "event_id": event.event_id,
            "observable_failure_reason": event.failure_reason,
            "observable_incident_flag": event.context.incident_flag,
            "observable_historic_recovery_rate": event.context.historic_recovery_rate,
            "observable_contacts_last_7_days": event.context.contacts_last_7_days,
            "predicted_probability_by_model": {
                name: model.score_actions(event, builder) for name, (model, builder) in models.items()
            },
        }
    return output


def _selection(models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for name, report in models.items():
        holdout = report["metrics"]["holdout"]["overall"]
        validation = report["metrics"]["validation"]["overall"]
        train = report["metrics"]["training"]["overall"]
        rows.append(
            {
                "model": name,
                "holdout_brier_score": holdout["brier_score"],
                "holdout_roc_auc": holdout["roc_auc"],
                "holdout_pr_auc": holdout["pr_auc"],
                "validation_brier_score": validation["brier_score"],
                "training_brier_score": train["brier_score"],
                "generalization_brier_gap": abs(train["brier_score"] - holdout["brier_score"]),
            }
        )
    # Probability quality is primary.  The remaining keys make the decision
    # deterministic without looking at Arena results or action diversity.
    selected = min(
        rows,
        key=lambda row: (
            round(row["holdout_brier_score"], 12),
            -round(row["holdout_pr_auc"], 12),
            round(row["generalization_brier_gap"], 12),
            ("baseline_logistic_regression", "interaction_logistic_regression", "gradient_boosted_stumps").index(row["model"]),
        ),
    )
    return {
        "rule": "minimum holdout Brier, then maximum holdout PR-AUC, then minimum train-holdout Brier gap, then simpler fixed candidate order",
        "arena_excluded": True,
        "selected_model": selected["model"],
        "comparison_rows": rows,
        "rationale": "The selected candidate has the best untouched-holdout probability quality under the fixed rule; Arena revenue and action diversity were not consulted.",
    }


def run_benchmark(config_path: Path, output_dir: Path, events_per_seed: int) -> dict[str, Any]:
    simulator = Simulator(SimulatorConfig.from_file(config_path))
    base_builder = build_feature_builder()
    interaction_builder = InteractionFeatureBuilder()
    specs = {
        split: DatasetSpec(split, seeds, events_per_seed) for split, seeds in SPLIT_SEEDS.items()
    }
    base_datasets = generate_experiment_datasets(simulator, specs, base_builder)
    interaction_datasets = generate_experiment_datasets(simulator, specs, interaction_builder)
    for split in specs:
        if base_datasets[split].event_ids != interaction_datasets[split].event_ids:
            raise RuntimeError(f"feature representation changed event grouping for {split}")

    metadata_common = {
        "experiment_version": "gate3.5_benchmark_v1.0.0",
        "training_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "simulator_version": simulator.config.simulator_version,
        "simulator_config_hash": simulator.config.config_hash,
        "seed_policy": {
            "training": [100000, 199999],
            "validation": [200000, 299999],
            "holdout": [300000, 399999],
            "arena_development_rejected": [400000, 499999],
            "arena_final_rejected": [900000, 999999],
        },
        "dataset_specs": {split: spec.to_dict() for split, spec in specs.items()},
        "protocol": "fit on training; fit Platt calibration on validation; freeze candidates; evaluate holdout once; no Arena evaluation",
    }

    baseline = RecoveryProbabilityModel.load(
        ROOT / "data" / "model_v1" / "recovery_model_v1.json",
        expected_simulator_version=simulator.config.simulator_version,
        expected_config_hash=simulator.config.config_hash,
        expected_schema=base_builder.schema,
    )
    interaction_metadata = {**metadata_common, "model_hyperparameters": {"type": "logistic_regression", "l2": 1e-4, "max_iterations": 80}}
    tree_metadata = {**metadata_common, "model_hyperparameters": {"type": "gradient_boosted_stumps", "learning_rate": 0.08, "n_estimators": 24, "max_thresholds_per_feature": 12, "l2": 1e-3, "random_seed": 0}}
    interaction = train_benchmark_model(
        INTERACTION_MODEL_VERSION,
        interaction_datasets["training"],
        interaction_datasets["validation"],
        simulator,
        interaction_builder.schema,
        interaction_metadata,
        classifier="interaction_logistic_regression",
    )
    tree = train_benchmark_model(
        TREE_MODEL_VERSION,
        interaction_datasets["training"],
        interaction_datasets["validation"],
        simulator,
        interaction_builder.schema,
        tree_metadata,
        classifier="gradient_boosted_stumps",
    )

    model_reports = {
        "baseline_logistic_regression": {
            "model_version": baseline.model_version,
            "feature_schema": base_builder.schema.to_dict(),
            "metrics": _evaluate(baseline, base_datasets, base_builder),
            "hyperparameters": {"type": "logistic_regression", "preserved_artifact": "data/model_v1/recovery_model_v1.json"},
        },
        "interaction_logistic_regression": {
            "model_version": interaction.model_version,
            "feature_schema": interaction_builder.schema.to_dict(),
            "metrics": _evaluate(interaction, interaction_datasets, interaction_builder),
            "hyperparameters": interaction_metadata["model_hyperparameters"],
        },
        "gradient_boosted_stumps": {
            "model_version": tree.model_version,
            "feature_schema": interaction_builder.schema.to_dict(),
            "metrics": _evaluate(tree, interaction_datasets, interaction_builder),
            "hyperparameters": tree_metadata["model_hyperparameters"],
        },
    }
    selection = _selection(model_reports)
    model_map = {
        "baseline_logistic_regression": (baseline, base_builder),
        "interaction_logistic_regression": (interaction, interaction_builder),
        "gradient_boosted_stumps": (tree, interaction_builder),
    }
    report = {
        "benchmark_version": "gate3.5_benchmark_v1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "simulator_version": simulator.config.simulator_version,
        "simulator_config_hash": simulator.config.config_hash,
        "models_benchmarked": list(model_reports),
        "data_manifest": _dataset_manifest(base_datasets),
        "interaction_data_manifest": _dataset_manifest(interaction_datasets),
        "training_protocol": metadata_common,
        "models": model_reports,
        "selection": selection,
        "action_context_sensitivity": _sensitivity(model_map, simulator),
        "arena_evaluation_performed": False,
        "arena_evaluation_note": "No new CHIMERA Arena evaluation was run for Gate 3.5 model selection.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    interaction.save(output_dir / "recovery_model_v2_interaction_lr.json")
    tree.save(output_dir / "recovery_model_v3_gradient_boosting.json")
    (output_dir / "benchmark_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "selection.json").write_text(json.dumps(selection, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "backend" / "configs" / "simulator_v1.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "model_benchmark_v1")
    parser.add_argument("--events-per-seed", type=int, default=500)
    args = parser.parse_args()
    report = run_benchmark(args.config, args.output_dir, args.events_per_seed)
    print(json.dumps({
        "models": report["models_benchmarked"],
        "datasets": report["data_manifest"],
        "selection": report["selection"],
        "arena_evaluation_performed": report["arena_evaluation_performed"],
        "output_dir": str(args.output_dir),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
