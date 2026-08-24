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
    llm_provider: str = "none"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 10.0


def load_settings() -> AppSettings:
    return AppSettings(
        database_url=os.getenv("DATABASE_URL", AppSettings.database_url),
        api_environment=os.getenv("API_ENVIRONMENT", "development"),
        model_artifact_path=Path(os.getenv("MODEL_ARTIFACT_PATH", str(AppSettings.model_artifact_path))),
        simulator_config_path=Path(os.getenv("SIMULATOR_CONFIG_PATH", str(AppSettings.simulator_config_path))),
        llm_provider=os.getenv("LLM_PROVIDER", "none"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "10")),
    )
