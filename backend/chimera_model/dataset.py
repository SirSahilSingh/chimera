"""Reproducible synthetic datasets for the Gate 3 model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from backend.chimera_simulator import Simulator
from backend.chimera_simulator.models import ACTIONS
from backend.chimera_simulator.seeds import validate_split_seed

from .features import ObservableFeatureBuilder


MODEL_SPLITS = ("training", "validation", "holdout")


class DatasetError(ValueError):
    """Raised when a model dataset request is invalid."""


@dataclass(frozen=True)
class DatasetSpec:
    split: str
    seeds: tuple[int, ...]
    events_per_seed: int

    def __post_init__(self) -> None:
        if self.split not in MODEL_SPLITS:
            raise DatasetError(
                f"model data may use only {MODEL_SPLITS}; Arena splits are evaluation-only"
            )
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise DatasetError("DatasetSpec requires one or more unique seeds")
        if isinstance(self.events_per_seed, bool) or not isinstance(self.events_per_seed, int) or self.events_per_seed <= 0:
            raise DatasetError("events_per_seed must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "seeds": list(self.seeds),
            "events_per_seed": self.events_per_seed,
        }


@dataclass(frozen=True)
class ModelDataset:
    split: str
    seeds: tuple[int, ...]
    events_per_seed: int
    event_ids: tuple[str, ...]
    row_event_ids: tuple[str, ...]
    row_actions: tuple[str, ...]
    feature_names: tuple[str, ...]
    features: np.ndarray
    labels: np.ndarray

    @property
    def event_count(self) -> int:
        return len(self.event_ids)

    @property
    def row_count(self) -> int:
        return int(self.labels.shape[0])

    @property
    def positive_count(self) -> int:
        return int(self.labels.sum())

    def manifest(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "seeds": list(self.seeds),
            "events_per_seed": self.events_per_seed,
            "event_count": self.event_count,
            "row_count": self.row_count,
            "positive_count": self.positive_count,
            "negative_count": self.row_count - self.positive_count,
            "positive_rate": self.positive_count / self.row_count if self.row_count else 0.0,
            "feature_count": len(self.feature_names),
        }


def generate_dataset(
    simulator: Simulator,
    spec: DatasetSpec,
    feature_builder: ObservableFeatureBuilder,
) -> ModelDataset:
    """Generate action-conditioned rows from observable events and simulator targets."""

    for seed in spec.seeds:
        validate_split_seed(simulator.config, spec.split, seed)

    event_ids: list[str] = []
    row_event_ids: list[str] = []
    row_actions: list[str] = []
    feature_rows: list[np.ndarray] = []
    labels: list[int] = []
    for seed in spec.seeds:
        cases = simulator.generate_batch(spec.split, seed, spec.events_per_seed)
        for case in cases:
            event = case.event
            event_ids.append(event.event_id)
            for action in ACTIONS:
                feature_rows.append(feature_builder.build_vector(event, action))
                row_event_ids.append(event.event_id)
                row_actions.append(action)
                # The outcome is the target only. It is never passed to the feature builder.
                labels.append(int(case.outcome.for_action(action).recovered))

    if not feature_rows:
        raise DatasetError("dataset contains no rows")
    return ModelDataset(
        split=spec.split,
        seeds=spec.seeds,
        events_per_seed=spec.events_per_seed,
        event_ids=tuple(event_ids),
        row_event_ids=tuple(row_event_ids),
        row_actions=tuple(row_actions),
        feature_names=feature_builder.schema.feature_names,
        features=np.vstack(feature_rows),
        labels=np.asarray(labels, dtype=np.float64),
    )


def generate_experiment_datasets(
    simulator: Simulator,
    specs: Mapping[str, DatasetSpec],
    feature_builder: ObservableFeatureBuilder,
) -> dict[str, ModelDataset]:
    required = set(MODEL_SPLITS)
    if set(specs) != required:
        raise DatasetError(f"experiment specs must define exactly {sorted(required)}")
    datasets = {
        split: generate_dataset(simulator, specs[split], feature_builder) for split in MODEL_SPLITS
    }
    event_ids_by_split = {split: set(dataset.event_ids) for split, dataset in datasets.items()}
    for split, event_ids in event_ids_by_split.items():
        for other_split, other_ids in event_ids_by_split.items():
            if split != other_split and event_ids.intersection(other_ids):
                raise DatasetError(f"exact event overlap between {split} and {other_split}")
    return datasets
