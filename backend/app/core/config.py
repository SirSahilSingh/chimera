from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class AppSettings:
    database_url: str = "postgresql+psycopg://chimera:chimera@localhost:5432/chimera"
    api_environment: str = "development"
    model_artifact_path: Path = REPOSITORY_ROOT / "data/model_benchmark_v1/recovery_model_v2_interaction_lr.json"
    simulator_config_path: Path = REPOSITORY_ROOT / "backend/configs/simulator_v1.yaml"


def load_settings() -> AppSettings:
    return AppSettings(
        database_url=os.getenv("DATABASE_URL", AppSettings.database_url),
        api_environment=os.getenv("API_ENVIRONMENT", "development"),
        model_artifact_path=Path(os.getenv("MODEL_ARTIFACT_PATH", str(AppSettings.model_artifact_path))),
        simulator_config_path=Path(os.getenv("SIMULATOR_CONFIG_PATH", str(AppSettings.simulator_config_path))),
    )
