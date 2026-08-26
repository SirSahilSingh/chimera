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
    voice_provider: str = "local"
    voice_enabled: bool = False
    voice_base_url: str | None = None
    voice_api_key: str | None = None
    voice_agent_id: str | None = None
    voice_phone_number: str | None = None
    voice_timeout_seconds: float = 10.0
    payment_provider: str = "local"
    payment_enabled: bool = True
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    payment_timeout_seconds: float = 10.0


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
        voice_provider=os.getenv("VOICE_PROVIDER", "local"),
        voice_enabled=os.getenv("VOICE_ENABLED", "false").casefold() in {"1", "true", "yes"},
        voice_base_url=os.getenv("VOICE_BASE_URL") or None,
        voice_api_key=os.getenv("VOICE_API_KEY") or None,
        voice_agent_id=os.getenv("VOICE_AGENT_ID") or None,
        voice_phone_number=os.getenv("VOICE_PHONE_NUMBER") or None,
        voice_timeout_seconds=float(os.getenv("VOICE_TIMEOUT_SECONDS", "10")),
        payment_provider=os.getenv("PAYMENT_PROVIDER", "local"),
        payment_enabled=os.getenv("PAYMENT_ENABLED", "true").casefold() in {"1", "true", "yes"},
        razorpay_key_id=os.getenv("RAZORPAY_KEY_ID") or None,
        razorpay_key_secret=os.getenv("RAZORPAY_KEY_SECRET") or None,
        razorpay_webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET") or None,
        payment_timeout_seconds=float(os.getenv("PAYMENT_TIMEOUT_SECONDS", "10")),
    )
