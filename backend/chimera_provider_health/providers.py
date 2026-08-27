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


def build_provider_specs(settings, *, voice_provider, payment_provider, messaging_provider, retry_provider) -> tuple[ProviderSpec, ...]:
    voice_live = voice_provider.name != "local"
    payment_live = payment_provider.name == "razorpay"
    messaging_live = messaging_provider.name == "twilio"
    voice_configured = (not voice_live) or all((settings.voice_enabled, settings.voice_base_url, settings.voice_api_key, settings.voice_agent_id, settings.voice_phone_number))
    payment_configured = (not payment_live) or all((settings.payment_enabled, settings.razorpay_key_id, settings.razorpay_key_secret))
    messaging_configured = (not messaging_live) or all((settings.messaging_enabled, settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number, settings.twilio_to_number))
    specs = (
        ProviderSpec(
            "voice", ProviderType.VOICE, voice_provider.name, str(voice_provider.mode).upper(), voice_configured, not voice_live,
            ("call_initiation", "call_status_updates", "conversation_events", "webhook_signature_verification"),
            ("Provider-neutral HTTP call API; production webhook URL and vendor-specific event mapping remain deployment responsibilities.",),
            getattr(voice_provider, "verify_connectivity", None),
        ),
        ProviderSpec(
            "razorpay", ProviderType.PAYMENTS, payment_provider.name, str(payment_provider.mode).upper(), payment_configured, not payment_live,
            ("payment_link_creation", "payment_status_reconciliation", "webhook_signature_verification"),
            ("No charge is created by readiness verification; a signed webhook remains the payment-recovery authority.",),
            getattr(payment_provider, "verify_connectivity", None),
        ),
        ProviderSpec(
            "twilio", ProviderType.MESSAGING, messaging_provider.name, str(messaging_provider.mode).upper(), messaging_configured, not messaging_live,
            ("outbound_messaging", "delivery_webhooks", "webhook_signature_verification"),
            ("Readiness verification does not send an SMS; sender and webhook configuration must be verified with Twilio.",),
            getattr(messaging_provider, "verify_connectivity", None),
        ),
        ProviderSpec(
            "retry", ProviderType.RETRY, retry_provider.name, str(retry_provider.mode).upper(), True, True,
            ("retry_execution_boundary",),
            ("Retry execution is provider-neutral in this repository; acceptance is not payment recovery.",),
            None,
        ),
        ProviderSpec(
            "escalation", ProviderType.ESCALATION, "operator_workflow", ProviderMode.LOCAL.value, True, True,
            ("operator_escalation_queue", "audit_events"),
            ("Escalation is an internal operator workflow and has no external provider connectivity.",),
            None,
        ),
    )
    return specs

