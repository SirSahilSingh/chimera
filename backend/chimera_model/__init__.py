"""Gate 3 recovery-probability modeling components."""

from .dataset import DatasetSpec, ModelDataset, generate_dataset, generate_experiment_datasets
from .features import (
    FEATURE_SCHEMA_VERSION,
    FeatureSchema,
    FeatureSchemaError,
    ForbiddenFeatureError,
    TemporalLeakageError,
    build_feature_builder,
)
from .model import ModelCompatibilityError, RecoveryProbabilityModel
from .benchmark import (
    BenchmarkProbabilityModel,
    Gate4ModelAdapter,
    GradientBoostedStumps,
    InteractionFeatureBuilder,
    INTERACTION_FEATURE_SCHEMA_VERSION,
    INTERACTION_MODEL_VERSION,
    TREE_MODEL_VERSION,
    train_benchmark_model,
)

__all__ = [
    "DatasetSpec",
    "FEATURE_SCHEMA_VERSION",
    "FeatureSchema",
    "FeatureSchemaError",
    "ForbiddenFeatureError",
    "ModelCompatibilityError",
    "ModelDataset",
    "RecoveryProbabilityModel",
    "BenchmarkProbabilityModel",
    "Gate4ModelAdapter",
    "GradientBoostedStumps",
    "InteractionFeatureBuilder",
    "INTERACTION_FEATURE_SCHEMA_VERSION",
    "INTERACTION_MODEL_VERSION",
    "TREE_MODEL_VERSION",
    "train_benchmark_model",
    "TemporalLeakageError",
    "build_feature_builder",
    "generate_dataset",
    "generate_experiment_datasets",
]
