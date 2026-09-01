from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI

from backend.app.api.v1.router import build_router
from backend.app.core.config import AppSettings, load_settings
from backend.app.core.database import create_schema, make_engine, make_session_factory
from backend.app.services.case_service import CaseService
from backend.app.services.journey_service import RecoveryJourneyService
from backend.app.services.intelligence_service import IntelligenceService
from backend.app.interventions.service import InterventionService
from backend.chimera_voice.provider import VoiceProvider, provider_from_settings as voice_provider_from_settings
from backend.chimera_voice.sarvam_provider import SarvamSpeechProvider
from backend.chimera_voice.service import VoiceService
from backend.chimera_payments.providers.local import LocalDeterministicPaymentProvider
from backend.chimera_payments.providers.razorpay import RazorpayPaymentProvider
from backend.chimera_payments.provider import PaymentProvider
from backend.chimera_payments.service import PaymentService
from backend.chimera_payments.order_service import PaymentOrderService
from backend.chimera_messaging.local_provider import LocalDeterministicMessagingProvider
from backend.chimera_messaging.twilio_provider import TwilioMessagingProvider
from backend.chimera_messaging.whatsapp_provider import WhatsAppMessagingProvider
from backend.chimera_messaging.service import MessagingService
from backend.chimera_retry.provider import LocalDeterministicRetryProvider, UnavailableLiveRetryProvider
from backend.chimera_retry.service import RetryService
from backend.provider_modes import resolve_mode
from backend.chimera_orchestration.service import RecoveryOrchestrator
from backend.chimera_orchestration.telegram_provider import TelegramEscalationProvider
from backend.chimera_intelligence.agent import ExplanationAgent
from backend.chimera_intelligence.provider import ExplanationProvider, provider_from_settings as explanation_provider_from_settings
from backend.chimera_intelligence.service import RecoveryIntelligenceService
from backend.chimera_model.benchmark import BenchmarkProbabilityModel, INTERACTION_FEATURE_SCHEMA_VERSION
from backend.chimera_simulator.config import SimulatorConfig
from backend.chimera_arena import ArenaComparisonService


def create_app(database_url: str | None = None, *, create_tables: bool = True, explanation_provider: ExplanationProvider | None = None, voice_provider: VoiceProvider | None = None) -> FastAPI:
    settings = load_settings()
    if database_url is not None:
        settings = AppSettings(
            database_url=database_url,
            api_environment=settings.api_environment,
            model_artifact_path=settings.model_artifact_path,
            simulator_config_path=settings.simulator_config_path,
            llm_provider=settings.llm_provider,
            llm_base_url=settings.llm_base_url,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
            llm_timeout_seconds=settings.llm_timeout_seconds,
            voice_provider=settings.voice_provider,
            voice_enabled=settings.voice_enabled,
            voice_base_url=settings.voice_base_url,
            voice_api_key=settings.voice_api_key,
            voice_agent_id=settings.voice_agent_id,
            voice_phone_number=settings.voice_phone_number,
            voice_timeout_seconds=settings.voice_timeout_seconds,
            voice_mode=settings.voice_mode,
            voice_public_base_url=settings.voice_public_base_url,
            voice_language=settings.voice_language,
            exotel_api_key=settings.exotel_api_key,
            exotel_api_token=settings.exotel_api_token,
            exotel_account_sid=settings.exotel_account_sid,
            exotel_flow_url=settings.exotel_flow_url,
            exotel_caller_id=settings.exotel_caller_id,
            exotel_api_base_url=settings.exotel_api_base_url,
            exotel_webhook_secret=settings.exotel_webhook_secret,
            sarvam_enabled=settings.sarvam_enabled,
            sarvam_api_key=settings.sarvam_api_key,
            sarvam_base_url=settings.sarvam_base_url,
            sarvam_language_code=settings.sarvam_language_code,
            sarvam_stt_model=settings.sarvam_stt_model,
            sarvam_stt_mode=settings.sarvam_stt_mode,
            sarvam_tts_model=settings.sarvam_tts_model,
            sarvam_tts_speaker=settings.sarvam_tts_speaker,
            sarvam_timeout_seconds=settings.sarvam_timeout_seconds,
            sarvam_mode=settings.sarvam_mode,
            payment_provider=settings.payment_provider,
            payment_enabled=settings.payment_enabled,
            razorpay_key_id=settings.razorpay_key_id,
            razorpay_key_secret=settings.razorpay_key_secret,
            razorpay_webhook_secret=settings.razorpay_webhook_secret,
            razorpay_mode=settings.razorpay_mode,
            payment_timeout_seconds=settings.payment_timeout_seconds,
            payment_mode=settings.payment_mode,
            messaging_provider=settings.messaging_provider,
            messaging_enabled=settings.messaging_enabled,
            twilio_account_sid=settings.twilio_account_sid,
            twilio_auth_token=settings.twilio_auth_token,
            twilio_from_number=settings.twilio_from_number,
            twilio_to_number=settings.twilio_to_number,
            messaging_channel=settings.messaging_channel,
            twilio_whatsapp_from_number=settings.twilio_whatsapp_from_number,
            twilio_whatsapp_to_number=settings.twilio_whatsapp_to_number,
            twilio_whatsapp_content_sid=settings.twilio_whatsapp_content_sid,
            messaging_public_base_url=settings.messaging_public_base_url,
            whatsapp_enabled=settings.whatsapp_enabled,
            whatsapp_access_token=settings.whatsapp_access_token,
            whatsapp_phone_number_id=settings.whatsapp_phone_number_id,
            whatsapp_to_number=settings.whatsapp_to_number,
            whatsapp_verify_token=settings.whatsapp_verify_token,
            whatsapp_app_secret=settings.whatsapp_app_secret,
            whatsapp_template_name=settings.whatsapp_template_name,
            whatsapp_template_language=settings.whatsapp_template_language,
            whatsapp_api_version=settings.whatsapp_api_version,
            whatsapp_mode=settings.whatsapp_mode,
            messaging_timeout_seconds=settings.messaging_timeout_seconds,
            messaging_mode=settings.messaging_mode,
            escalation_provider=settings.escalation_provider,
            escalation_enabled=settings.escalation_enabled,
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
            escalation_timeout_seconds=settings.escalation_timeout_seconds,
            escalation_mode=settings.escalation_mode,
            retry_provider=settings.retry_provider,
            retry_mode=settings.retry_mode,
            allow_live_execution=settings.allow_live_execution,
        )
    engine = make_engine(settings.database_url)
    if create_tables:
        create_schema(engine)
    session_factory = make_session_factory(engine)
    simulator_config = SimulatorConfig.from_file(settings.simulator_config_path)
    agent = ExplanationAgent(explanation_provider if explanation_provider is not None else explanation_provider_from_settings(settings))
    configured_voice_provider = voice_provider if voice_provider is not None else voice_provider_from_settings(settings)
    configured_speech_provider = SarvamSpeechProvider(
        settings.sarvam_api_key,
        enabled=settings.sarvam_enabled,
        timeout_seconds=settings.sarvam_timeout_seconds,
        base_url=settings.sarvam_base_url,
        language_code=settings.sarvam_language_code,
        stt_model=settings.sarvam_stt_model,
        stt_mode=settings.sarvam_stt_mode,
        tts_model=settings.sarvam_tts_model,
        tts_speaker=settings.sarvam_tts_speaker,
        mode=settings.sarvam_mode,
    )
    if settings.voice_mode:
        configured_voice_provider.mode = resolve_mode(configured_voice_provider.name, settings.voice_mode)
    if configured_voice_provider.mode == "LIVE" and not settings.allow_live_execution and hasattr(configured_voice_provider, "enabled"):
        configured_voice_provider.enabled = False
    if settings.payment_provider == "razorpay":
        configured_payment_provider: PaymentProvider = RazorpayPaymentProvider(settings.razorpay_key_id, settings.razorpay_key_secret, settings.razorpay_webhook_secret, enabled=settings.payment_enabled, timeout_seconds=settings.payment_timeout_seconds, mode=settings.razorpay_mode)
    else:
        configured_payment_provider = LocalDeterministicPaymentProvider()
        if settings.payment_mode:
            configured_payment_provider.mode = resolve_mode(configured_payment_provider.name, settings.payment_mode)
    if configured_payment_provider.mode == "LIVE" and not settings.allow_live_execution and hasattr(configured_payment_provider, "enabled"):
        configured_payment_provider.enabled = False
    if settings.messaging_provider == "twilio":
        twilio_whatsapp = settings.messaging_channel == "whatsapp"
        twilio_from_number = settings.twilio_whatsapp_from_number if twilio_whatsapp else settings.twilio_from_number
        twilio_to_number = settings.twilio_whatsapp_to_number if twilio_whatsapp else settings.twilio_to_number
        messaging_public_base_url = settings.messaging_public_base_url or settings.voice_public_base_url
        status_callback_url = f"{messaging_public_base_url.rstrip('/')}/api/v1/messaging/webhook/twilio" if messaging_public_base_url else None
        configured_messaging_provider = TwilioMessagingProvider(settings.twilio_account_sid, settings.twilio_auth_token, twilio_from_number, twilio_to_number, enabled=settings.messaging_enabled, timeout_seconds=settings.messaging_timeout_seconds, content_sid=settings.twilio_whatsapp_content_sid, status_callback_url=status_callback_url, whatsapp=twilio_whatsapp, mode=settings.messaging_mode)
    elif settings.messaging_provider == "whatsapp":
        configured_messaging_provider = WhatsAppMessagingProvider(settings.whatsapp_access_token, settings.whatsapp_phone_number_id, settings.whatsapp_to_number, settings.whatsapp_verify_token, settings.whatsapp_app_secret, enabled=settings.messaging_enabled and settings.whatsapp_enabled, timeout_seconds=settings.messaging_timeout_seconds, api_version=settings.whatsapp_api_version, template_name=settings.whatsapp_template_name, template_language=settings.whatsapp_template_language, mode=settings.whatsapp_mode)
    else:
        configured_messaging_provider = LocalDeterministicMessagingProvider()
        if settings.messaging_mode:
            configured_messaging_provider.mode = resolve_mode(configured_messaging_provider.name, settings.messaging_mode)
    if configured_messaging_provider.mode == "LIVE" and not settings.allow_live_execution and hasattr(configured_messaging_provider, "enabled"):
        configured_messaging_provider.enabled = False
    configured_escalation_provider = TelegramEscalationProvider(settings.telegram_bot_token, settings.telegram_chat_id, enabled=settings.escalation_enabled, timeout_seconds=settings.escalation_timeout_seconds, mode=settings.escalation_mode) if settings.escalation_provider.casefold() == "telegram" else None
    configured_retry_provider = UnavailableLiveRetryProvider() if settings.retry_provider == "live" else LocalDeterministicRetryProvider()
    if settings.retry_mode:
        configured_retry_provider.mode = resolve_mode(configured_retry_provider.name, settings.retry_mode)

    @lru_cache(maxsize=1)
    def compatibility_status() -> str:
        try:
            BenchmarkProbabilityModel.load(settings.model_artifact_path, expected_simulator_version=simulator_config.simulator_version, expected_config_hash=simulator_config.config_hash)
            return "compatible"
        except Exception:
            return "incompatible"

    def service_factory(session):
        return CaseService(session, simulator_config, settings.model_artifact_path)

    def health_factory():
        return engine, settings, compatibility_status()

    def intelligence_service_factory(session):
        return IntelligenceService(session, simulator_config, agent)

    def recovery_intelligence_service_factory(session):
        return RecoveryIntelligenceService(RecoveryJourneyService(session), simulator_config)

    def intervention_service_factory(session):
        return InterventionService(session)

    def payment_service_factory(session):
        return PaymentService(session, configured_payment_provider, demo_enabled=settings.api_environment != "production", enabled=settings.payment_enabled)

    def payment_order_service_factory(session):
        return PaymentOrderService(
            session,
            configured_payment_provider,
            case_service=service_factory(session),
            intervention_service=intervention_service_factory(session),
            orchestrator=orchestration_service_factory(session),
        )

    def voice_service_factory(session):
        return VoiceService(session, configured_voice_provider, payment_service=payment_service_factory(session), messaging_service=messaging_service_factory(session), speech_provider=configured_speech_provider)

    def messaging_service_factory(session):
        return MessagingService(session, configured_messaging_provider, payment_service=payment_service_factory(session))

    def retry_service_factory(session):
        return RetryService(session, configured_retry_provider)

    def orchestration_service_factory(session):
        return RecoveryOrchestrator(session, messaging_service_factory(session), retry_service_factory(session), payment_service_factory(session), voice_service_factory(session), case_service=service_factory(session), escalation_provider=configured_escalation_provider)

    def provider_health_service_factory(session):
        from backend.chimera_provider_health.service import ProviderHealthService
        return ProviderHealthService(
            session,
            settings=settings,
            voice_provider=configured_voice_provider,
            payment_provider=configured_payment_provider,
            messaging_provider=configured_messaging_provider,
            retry_provider=configured_retry_provider,
            escalation_provider=configured_escalation_provider,
            speech_provider=configured_speech_provider,
        )

    def arena_service_factory():
        return ArenaComparisonService(simulator_config, settings.model_artifact_path)

    app = FastAPI(title="CHIMERA API", version="1.0.0")
    router = build_router(
        session_factory=session_factory,
        service_factory=service_factory,
        health_factory=health_factory,
        intelligence_service_factory=intelligence_service_factory,
        recovery_intelligence_service_factory=recovery_intelligence_service_factory,
        intervention_service_factory=intervention_service_factory,
        voice_service_factory=voice_service_factory,
        payment_service_factory=payment_service_factory,
        payment_order_service_factory=payment_order_service_factory,
        orchestration_service_factory=orchestration_service_factory,
        provider_health_service_factory=provider_health_service_factory,
        arena_service_factory=arena_service_factory,
    )
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="")
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.settings = settings
    app.state.explanation_agent = agent
    app.state.voice_provider = configured_voice_provider
    app.state.speech_provider = configured_speech_provider
    app.state.payment_provider = configured_payment_provider
    app.state.messaging_provider = configured_messaging_provider
    app.state.retry_provider = configured_retry_provider
    return app


# Keep module importable for local tests and schema tooling when PostgreSQL's
# optional driver is not installed. Deployments set DATABASE_URL explicitly.
app = create_app(database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"), create_tables=False)
