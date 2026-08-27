from __future__ import annotations

from enum import StrEnum


class ProviderMode(StrEnum):
    LOCAL = "LOCAL"
    MOCK = "MOCK"
    TEST = "TEST"
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


PROVIDER_MODE_LABELS = {
    ProviderMode.LOCAL.value: "Demo Voice Agent",
    ProviderMode.MOCK.value: "Simulated Payment Provider",
    ProviderMode.TEST.value: "Provider Test Mode",
    ProviderMode.SANDBOX.value: "Provider Sandbox Mode",
    ProviderMode.LIVE.value: "Live Provider Execution",
}

SAFE_PROVIDER_FAILURE_CODES = frozenset({
    "provider_not_configured",
    "provider_disabled",
    "provider_timeout",
    "provider_unavailable",
    "provider_invalid_response",
    "provider_invalid_webhook",
    "provider_request_failed",
    "invalid_webhook_signature",
    "invalid_webhook_payload",
    "payment_service_unavailable",
    "voice_disabled",
    "missing_configuration",
    "demo_requires_local_provider",
    "provider_failure",
})


def mode_label(mode: str, provider: str | None = None) -> str:
    normalized = str(mode).upper()
    if normalized == ProviderMode.LOCAL.value and provider:
        local_labels = {
            "voice": "Demo Voice Agent",
            "local": "Demo Provider Execution",
        }
        return local_labels.get(str(provider).casefold(), "Demo Provider Execution")
    return PROVIDER_MODE_LABELS.get(normalized, "Provider Execution")


def safe_failure_code(value: object, default: str = "provider_failure") -> str:
    candidate = str(value).strip().casefold()
    return candidate if candidate in SAFE_PROVIDER_FAILURE_CODES else default


def resolve_mode(provider: str, configured: str | None = None) -> str:
    if configured:
        return ProviderMode(configured.upper()).value
    return ProviderMode.LOCAL.value if provider.casefold() == "local" else ProviderMode.LIVE.value
