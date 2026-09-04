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
    voice_public_base_url: str | None = None
    voice_language: str = "hi-IN"
    exotel_api_key: str | None = None
    exotel_api_token: str | None = None
    exotel_account_sid: str | None = None
    exotel_app_id: str | None = None
    exotel_flow_url: str | None = None
    exotel_caller_id: str | None = None
    exotel_api_base_url: str = "https://api.in.exotel.com"
    exotel_portal_base_url: str = "https://my.exotel.com"
    exotel_webhook_secret: str | None = None
    exotel_agentstream_enabled: bool = False
    exotel_stream_url: str | None = None
    vobiz_auth_id: str | None = None
    vobiz_auth_token: str | None = None
    vobiz_caller_id: str | None = None
    vobiz_api_base_url: str = "https://api.vobiz.ai"
    vobiz_stream_url: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    sarvam_enabled: bool = False
    sarvam_api_key: str | None = None
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_language_code: str = "hi-IN"
    sarvam_stt_model: str = "saaras:v3"
    sarvam_stt_mode: str = "codemix"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"
    sarvam_timeout_seconds: float = 20.0
    sarvam_mode: str | None = None
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
    messaging_channel: str = "sms"
    twilio_whatsapp_from_number: str | None = None
    twilio_whatsapp_to_number: str | None = None
    twilio_whatsapp_content_sid: str | None = None
    messaging_public_base_url: str | None = None
    whatsapp_enabled: bool = False
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_to_number: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_template_name: str | None = None
    whatsapp_template_language: str = "en_US"
    whatsapp_api_version: str = "v23.0"
    whatsapp_mode: str | None = None
    messaging_timeout_seconds: float = 10.0
    messaging_mode: str | None = None
    escalation_provider: str = "local"
    escalation_enabled: bool = True
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    escalation_timeout_seconds: float = 10.0
    escalation_mode: str | None = None
    retry_provider: str = "local"
    retry_mode: str | None = None
    allow_live_execution: bool = False


def _load_env_file() -> None:
    """Lightweight .env loader without third-party dependencies."""
    for env_path in (REPOSITORY_ROOT / ".env", REPOSITORY_ROOT / "backend/.env"):
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
                        continue
                    key, _, value = trimmed.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            except Exception:
                pass


def load_settings() -> AppSettings:
    _load_env_file()
    raw_public_base = os.getenv("VOICE_PUBLIC_BASE_URL") or None
    if raw_public_base:
        voice_public_base_url = raw_public_base.strip().rstrip("/")
        if voice_public_base_url.endswith("/api/v1"):
            voice_public_base_url = voice_public_base_url[:-len("/api/v1")].rstrip("/")
    else:
        voice_public_base_url = None

    exotel_stream_url = os.getenv("EXOTEL_STREAM_URL")
    if not exotel_stream_url and voice_public_base_url:
        wss_base = voice_public_base_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
        exotel_stream_url = f"{wss_base}/api/v1/voice/exotel/stream"

    sarvam_api_key = os.getenv("SARVAM_API_KEY") or None
    sarvam_enabled_raw = os.getenv("SARVAM_ENABLED")
    sarvam_enabled = (
        sarvam_enabled_raw.casefold() in {"1", "true", "yes"}
        if sarvam_enabled_raw is not None
        else bool(sarvam_api_key)
    )

    vobiz_auth_id = os.getenv("VOBIZ_AUTH_ID") or None
    vobiz_auth_token = os.getenv("VOBIZ_AUTH_TOKEN") or None
    vobiz_caller_id = os.getenv("VOBIZ_CALLER_ID") or os.getenv("VOBIZ_FROM_NUMBER") or None
    vobiz_stream_url = os.getenv("VOBIZ_STREAM_URL")
    if not vobiz_stream_url and voice_public_base_url:
        wss_base = voice_public_base_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
        vobiz_stream_url = f"{wss_base}/api/v1/voice/vobiz/stream"

    exotel_api_key = os.getenv("EXOTEL_API_KEY") or None
    exotel_account_sid = os.getenv("EXOTEL_ACCOUNT_SID") or None
    voice_provider = os.getenv("VOICE_PROVIDER")
    if not voice_provider and vobiz_auth_id and vobiz_auth_token:
        voice_provider = "vobiz"
    elif not voice_provider and exotel_api_key and exotel_account_sid:
        voice_provider = "exotel"
    elif not voice_provider:
        voice_provider = "local"

    voice_enabled_raw = os.getenv("VOICE_ENABLED")
    if voice_enabled_raw is not None:
        voice_enabled = voice_enabled_raw.casefold() in {"1", "true", "yes"}
    elif voice_provider == "vobiz":
        voice_enabled = bool(vobiz_auth_id and vobiz_auth_token)
    elif voice_provider == "exotel":
        voice_enabled = bool(exotel_api_key and exotel_account_sid)
    else:
        voice_enabled = False

    razorpay_key_id = os.getenv("RAZORPAY_KEY_ID") or None
    razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET") or None
    payment_provider = os.getenv("PAYMENT_PROVIDER")
    if not payment_provider and razorpay_key_id and razorpay_key_secret:
        payment_provider = "razorpay"
    elif not payment_provider:
        payment_provider = "local"

    payment_enabled_raw = os.getenv("PAYMENT_ENABLED")
    if payment_enabled_raw is not None:
        payment_enabled = payment_enabled_raw.casefold() in {"1", "true", "yes"}
    elif payment_provider == "razorpay":
        payment_enabled = bool(razorpay_key_id and razorpay_key_secret)
    else:
        payment_enabled = True

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
        voice_provider=voice_provider,
        voice_enabled=voice_enabled,
        voice_base_url=os.getenv("VOICE_BASE_URL") or None,
        voice_api_key=os.getenv("VOICE_API_KEY") or None,
        voice_agent_id=os.getenv("VOICE_AGENT_ID") or None,
        voice_phone_number=os.getenv("VOICE_PHONE_NUMBER") or None,
        voice_timeout_seconds=float(os.getenv("VOICE_TIMEOUT_SECONDS", "10")),
        voice_mode=os.getenv("VOICE_MODE") or None,
        voice_public_base_url=voice_public_base_url,
        voice_language=os.getenv("VOICE_LANGUAGE", "hi-IN"),
        exotel_api_key=exotel_api_key,
        exotel_api_token=os.getenv("EXOTEL_API_TOKEN") or None,
        exotel_account_sid=exotel_account_sid,
        exotel_app_id=os.getenv("EXOTEL_APP_ID") or None,
        exotel_flow_url=(
            os.getenv("EXOTEL_FLOW_URL")
            or (
                f"{os.getenv('EXOTEL_PORTAL_BASE_URL', 'https://my.exotel.com').rstrip('/')}/"
                f"{exotel_account_sid}/exoml/start_voice/{os.getenv('EXOTEL_APP_ID')}"
                if exotel_account_sid and os.getenv("EXOTEL_APP_ID")
                else None
            )
        ),
        exotel_caller_id=os.getenv("EXOTEL_CALLER_ID") or None,
        exotel_api_base_url=os.getenv("EXOTEL_API_BASE_URL", "https://api.in.exotel.com").rstrip("/"),
        exotel_portal_base_url=os.getenv("EXOTEL_PORTAL_BASE_URL", "https://my.exotel.com").rstrip("/"),
        exotel_webhook_secret=os.getenv("EXOTEL_WEBHOOK_SECRET") or None,
        exotel_agentstream_enabled=os.getenv("EXOTEL_AGENTSTREAM_ENABLED", "false").casefold() in {"1", "true", "yes"},
        exotel_stream_url=exotel_stream_url,
        vobiz_auth_id=vobiz_auth_id,
        vobiz_auth_token=vobiz_auth_token,
        vobiz_caller_id=vobiz_caller_id,
        vobiz_api_base_url=os.getenv("VOBIZ_API_BASE_URL", "https://api.vobiz.ai").rstrip("/"),
        vobiz_stream_url=vobiz_stream_url,
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        sarvam_enabled=sarvam_enabled,
        sarvam_api_key=sarvam_api_key,
        sarvam_base_url=os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai"),
        sarvam_language_code=os.getenv("SARVAM_LANGUAGE_CODE", "hi-IN"),
        sarvam_stt_model=os.getenv("SARVAM_STT_MODEL", "saaras:v3"),
        sarvam_stt_mode=os.getenv("SARVAM_STT_MODE", "codemix"),
        sarvam_tts_model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
        sarvam_tts_speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
        sarvam_timeout_seconds=float(os.getenv("SARVAM_TIMEOUT_SECONDS", "20")),
        sarvam_mode=os.getenv("SARVAM_MODE") or None,
        payment_provider=payment_provider,
        payment_enabled=payment_enabled,
        razorpay_key_id=razorpay_key_id,
        razorpay_key_secret=razorpay_key_secret,
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
        messaging_channel=os.getenv("MESSAGING_CHANNEL", "sms").casefold(),
        twilio_whatsapp_from_number=os.getenv("TWILIO_WHATSAPP_FROM_NUMBER") or None,
        twilio_whatsapp_to_number=os.getenv("TWILIO_WHATSAPP_TO_NUMBER") or None,
        twilio_whatsapp_content_sid=os.getenv("TWILIO_WHATSAPP_CONTENT_SID") or None,
        messaging_public_base_url=os.getenv("MESSAGING_PUBLIC_BASE_URL") or None,
        whatsapp_enabled=os.getenv("WHATSAPP_ENABLED", "false").casefold() in {"1", "true", "yes"},
        whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN") or None,
        whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID") or None,
        whatsapp_to_number=os.getenv("WHATSAPP_TO_NUMBER") or None,
        whatsapp_verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN") or None,
        whatsapp_app_secret=os.getenv("WHATSAPP_APP_SECRET") or None,
        whatsapp_template_name=os.getenv("WHATSAPP_TEMPLATE_NAME") or None,
        whatsapp_template_language=os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en_US"),
        whatsapp_api_version=os.getenv("WHATSAPP_API_VERSION", "v23.0"),
        whatsapp_mode=os.getenv("WHATSAPP_MODE") or None,
        messaging_timeout_seconds=float(os.getenv("MESSAGING_TIMEOUT_SECONDS", "10")),
        messaging_mode=os.getenv("MESSAGING_MODE") or None,
        escalation_provider=os.getenv("ESCALATION_PROVIDER", "local"),
        escalation_enabled=os.getenv("ESCALATION_ENABLED", "true").casefold() in {"1", "true", "yes"},
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        escalation_timeout_seconds=float(os.getenv("ESCALATION_TIMEOUT_SECONDS", "10")),
        escalation_mode=os.getenv("ESCALATION_MODE") or None,
        retry_provider=os.getenv("RETRY_PROVIDER", "local"),
        retry_mode=os.getenv("RETRY_MODE") or None,
        allow_live_execution=os.getenv("CHIMERA_ALLOW_LIVE_EXECUTION", "false").casefold() in {"1", "true", "yes"},
    )
