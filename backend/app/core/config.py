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
    voice_mode: str | None = None
    payment_provider: str = "local"
    payment_enabled: bool = True
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    razorpay_mode: str | None = None
    payment_timeout_seconds: float = 10.0
    payment_mode: str | None = None
    messaging_provider: str = "local"
    messaging_enabled: bool = True
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    twilio_to_number: str | None = None
    messaging_timeout_seconds: float = 10.0
    messaging_mode: str | None = None
    retry_provider: str = "local"
    retry_mode: str | None = None
    allow_live_execution: bool = False


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
        voice_mode=os.getenv("VOICE_MODE") or None,
        payment_provider=os.getenv("PAYMENT_PROVIDER", "local"),
        payment_enabled=os.getenv("PAYMENT_ENABLED", "true").casefold() in {"1", "true", "yes"},
        razorpay_key_id=os.getenv("RAZORPAY_KEY_ID") or None,
        razorpay_key_secret=os.getenv("RAZORPAY_KEY_SECRET") or None,
        razorpay_webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET") or None,
        razorpay_mode=os.getenv("RAZORPAY_MODE") or os.getenv("PAYMENT_MODE") or None,
        payment_timeout_seconds=float(os.getenv("PAYMENT_TIMEOUT_SECONDS", "10")),
        payment_mode=os.getenv("PAYMENT_MODE") or None,
        messaging_provider=os.getenv("MESSAGING_PROVIDER", "local"),
        messaging_enabled=os.getenv("MESSAGING_ENABLED", "true").casefold() in {"1", "true", "yes"},
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN") or None,
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER") or None,
        twilio_to_number=os.getenv("TWILIO_TO_NUMBER") or None,
        messaging_timeout_seconds=float(os.getenv("MESSAGING_TIMEOUT_SECONDS", "10")),
        messaging_mode=os.getenv("MESSAGING_MODE") or None,
        retry_provider=os.getenv("RETRY_PROVIDER", "local"),
        retry_mode=os.getenv("RETRY_MODE") or None,
        allow_live_execution=os.getenv("CHIMERA_ALLOW_LIVE_EXECUTION", "false").casefold() in {"1", "true", "yes"},
    )
