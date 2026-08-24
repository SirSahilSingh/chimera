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

__all__ = [
    "DatasetSpec",
    "FEATURE_SCHEMA_VERSION",
    "FeatureSchema",
    "FeatureSchemaError",
    "ForbiddenFeatureError",
    "ModelCompatibilityError",
    "ModelDataset",
    "RecoveryProbabilityModel",
    "TemporalLeakageError",
    "build_feature_builder",
    "generate_dataset",
    "generate_experiment_datasets",
]
