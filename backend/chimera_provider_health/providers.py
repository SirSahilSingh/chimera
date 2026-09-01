from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.provider_modes import ProviderMode

from .schemas import ProviderType


@dataclass(frozen=True)
class ProviderSpec:
    provider_name: str
    provider_type: ProviderType
    implementation: str
    provider_mode: str
    configured: bool
    is_local: bool
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    probe: Callable[[], None] | None

    @property
    def safe_identity(self) -> dict[str, object]:
        return {
            "provider_name": self.provider_name,
            "provider_type": self.provider_type.value,
            "implementation": self.implementation,
            "provider_mode": self.provider_mode,
            "configured": self.configured,
            "capabilities": self.capabilities,
        }


def build_provider_specs(settings, *, voice_provider, payment_provider, messaging_provider, retry_provider, escalation_provider=None, speech_provider=None) -> tuple[ProviderSpec, ...]:
    voice_live = voice_provider.name != "local"
    payment_live = payment_provider.name == "razorpay"
    messaging_live = messaging_provider.name in {"twilio", "whatsapp"}
    voice_configured = (not voice_live) or (
        all((settings.voice_enabled, settings.twilio_account_sid, settings.twilio_auth_token, settings.voice_phone_number, settings.voice_public_base_url, getattr(settings, "sarvam_enabled", False), getattr(settings, "sarvam_api_key", None)))
        if voice_provider.name == "twilio"
        else all((settings.voice_enabled, getattr(settings, "exotel_api_key", None), getattr(settings, "exotel_api_token", None), getattr(settings, "exotel_account_sid", None), getattr(settings, "exotel_flow_url", None), getattr(settings, "exotel_caller_id", None), settings.voice_public_base_url))
        if voice_provider.name == "exotel"
        else all((settings.voice_enabled, settings.voice_base_url, settings.voice_api_key, settings.voice_agent_id, settings.voice_phone_number))
    )
    payment_configured = (not payment_live) or all((settings.payment_enabled, settings.razorpay_key_id, settings.razorpay_key_secret))
    messaging_configured = (not messaging_live) or (
        (all((settings.messaging_enabled, settings.twilio_account_sid, settings.twilio_auth_token, getattr(settings, "twilio_whatsapp_from_number", None))) if getattr(settings, "messaging_channel", "sms") == "whatsapp" else all((settings.messaging_enabled, settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number, settings.twilio_to_number)))
        if messaging_provider.name == "twilio"
        else all((settings.messaging_enabled, settings.whatsapp_enabled, settings.whatsapp_access_token, settings.whatsapp_phone_number_id))
    )
    escalation_live = escalation_provider is not None
    escalation_configured = (not escalation_live) or all((settings.escalation_enabled, settings.telegram_bot_token, settings.telegram_chat_id))
    messaging_health_name = "whatsapp" if messaging_provider.name == "whatsapp" else "twilio"
    messaging_implementation = f"{messaging_provider.name}/{getattr(settings, 'messaging_channel', 'sms')}" if messaging_provider.name == "twilio" else messaging_provider.name
    voice_implementation = f"{voice_provider.name}+{speech_provider.name}" if speech_provider is not None and voice_provider.name == "twilio" else voice_provider.name
    voice_capabilities = ("call_initiation", "call_status_updates", "conversation_events", "webhook_signature_verification")
    if voice_provider.name == "twilio":
        voice_capabilities += ("sarvam_hinglish_stt", "sarvam_hinglish_tts")
    if voice_provider.name == "exotel":
        voice_capabilities += ("exotel_call_flow", "exotel_status_callbacks")
    specs = (
        ProviderSpec(
            "voice", ProviderType.VOICE, voice_implementation, str(voice_provider.mode).upper(), voice_configured, not voice_live,
            voice_capabilities,
            (("Exotel provides phone transport and call-flow execution; CHIMERA receives status callbacks. A verified trial destination, Exotel flow, credentials, and public callback URL are required for real calls.",) if voice_provider.name == "exotel" else ("Twilio provides phone transport; Sarvam Saaras/Bulbul provide the Hinglish speech loop. Both credentials and a public callback URL are required for real calls.",)),
            getattr(voice_provider, "verify_connectivity", None),
        ),
        ProviderSpec(
            "razorpay", ProviderType.PAYMENTS, payment_provider.name, str(payment_provider.mode).upper(), payment_configured, not payment_live,
            ("payment_link_creation", "payment_status_reconciliation", "webhook_signature_verification"),
            ("No charge is created by readiness verification; a signed webhook remains the payment-recovery authority.",),
            getattr(payment_provider, "verify_connectivity", None),
        ),
        ProviderSpec(
            messaging_health_name, ProviderType.MESSAGING, messaging_implementation, str(messaging_provider.mode).upper(), messaging_configured, not messaging_live,
            ("outbound_messaging", "delivery_webhooks", "webhook_signature_verification"),
            ("Readiness verification does not send a customer message; sender, recipient policy, and webhook configuration remain provider responsibilities.",),
            getattr(messaging_provider, "verify_connectivity", None),
        ),
        ProviderSpec(
            "retry", ProviderType.RETRY, retry_provider.name, str(retry_provider.mode).upper(), True, True,
            ("retry_execution_boundary",),
            ("Retry execution is provider-neutral in this repository; acceptance is not payment recovery.",),
            None,
        ),
        ProviderSpec(
            "escalation", ProviderType.ESCALATION, getattr(escalation_provider, "name", "operator_workflow"), str(getattr(escalation_provider, "mode", ProviderMode.LOCAL.value)).upper(), escalation_configured, not escalation_live,
            ("operator_escalation_queue", "audit_events") + (("operator_notification",) if escalation_live else ()),
            ("Telegram notification is optional; the internal escalation queue remains available if it is not configured.",),
            getattr(escalation_provider, "verify_connectivity", None),
        ),
    )
    return specs
