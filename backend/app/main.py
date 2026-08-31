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
from backend.chimera_voice.service import VoiceService
from backend.chimera_payments.providers.local import LocalDeterministicPaymentProvider
from backend.chimera_payments.providers.razorpay import RazorpayPaymentProvider
from backend.chimera_payments.provider import PaymentProvider
from backend.chimera_payments.service import PaymentService
from backend.chimera_messaging.local_provider import LocalDeterministicMessagingProvider
from backend.chimera_messaging.twilio_provider import TwilioMessagingProvider
from backend.chimera_messaging.service import MessagingService
from backend.chimera_retry.provider import LocalDeterministicRetryProvider, UnavailableLiveRetryProvider
from backend.chimera_retry.service import RetryService
from backend.provider_modes import resolve_mode
from backend.chimera_orchestration.service import RecoveryOrchestrator
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
            messaging_timeout_seconds=settings.messaging_timeout_seconds,
            messaging_mode=settings.messaging_mode,
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
        configured_messaging_provider = TwilioMessagingProvider(settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number, settings.twilio_to_number, enabled=settings.messaging_enabled, timeout_seconds=settings.messaging_timeout_seconds, mode=settings.messaging_mode)
    else:
        configured_messaging_provider = LocalDeterministicMessagingProvider()
        if settings.messaging_mode:
            configured_messaging_provider.mode = resolve_mode(configured_messaging_provider.name, settings.messaging_mode)
    if configured_messaging_provider.mode == "LIVE" and not settings.allow_live_execution and hasattr(configured_messaging_provider, "enabled"):
        configured_messaging_provider.enabled = False
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

    def voice_service_factory(session):
        return VoiceService(session, configured_voice_provider, payment_service=payment_service_factory(session))

    def messaging_service_factory(session):
        return MessagingService(session, configured_messaging_provider, payment_service=payment_service_factory(session))

    def retry_service_factory(session):
        return RetryService(session, configured_retry_provider)

    def orchestration_service_factory(session):
        return RecoveryOrchestrator(session, messaging_service_factory(session), retry_service_factory(session), payment_service_factory(session), voice_service_factory(session), case_service=service_factory(session))

    def provider_health_service_factory(session):
        from backend.chimera_provider_health.service import ProviderHealthService
        return ProviderHealthService(
            session,
            settings=settings,
            voice_provider=configured_voice_provider,
            payment_provider=configured_payment_provider,
            messaging_provider=configured_messaging_provider,
            retry_provider=configured_retry_provider,
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
    app.state.payment_provider = configured_payment_provider
    app.state.messaging_provider = configured_messaging_provider
    app.state.retry_provider = configured_retry_provider
    return app


# Keep module importable for local tests and schema tooling when PostgreSQL's
# optional driver is not installed. Deployments set DATABASE_URL explicitly.
app = create_app(database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"), create_tables=False)
