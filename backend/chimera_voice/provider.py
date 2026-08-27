from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .context import context_hash
from .schemas import VoiceContext, VoiceScenario, VoiceWebhookEvent


class VoiceProviderError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VoiceCallStartResult:
    provider: str
    provider_call_reference: str


class VoiceProvider:
    name = "base"
    mode = "LIVE"

    def start_call(self, context: VoiceContext, *, idempotency_key: str, scenario: VoiceScenario) -> VoiceCallStartResult:
        raise NotImplementedError

    def receive_event(self, provider_call_reference: str, event_type: str) -> None:
        del provider_call_reference, event_type

    def end_call(self, provider_call_reference: str) -> None:
        del provider_call_reference

    def verify_webhook(self, event: VoiceWebhookEvent) -> bool:
        del event
        return False

    def verify_connectivity(self) -> None:
        """Optional side-effect-free provider readiness probe."""
        raise VoiceProviderError("unsupported_capability")


class LocalDeterministicVoiceProvider(VoiceProvider):
    name = "local"
    mode = "LOCAL"

    def start_call(self, context: VoiceContext, *, idempotency_key: str, scenario: VoiceScenario) -> VoiceCallStartResult:
        if scenario == VoiceScenario.PROVIDER_FAILURE:
            raise VoiceProviderError("provider_failure")
        material = f"local-voice-v1|{idempotency_key}|{scenario.value}|{context_hash(context)}"
        reference = f"local-call:{hashlib.sha256(material.encode('utf-8')).hexdigest()[:32]}"
        return VoiceCallStartResult(provider=self.name, provider_call_reference=reference)

    def verify_webhook(self, event: VoiceWebhookEvent) -> bool:
        expected = sign_webhook_event(event)
        return hmac.compare_digest(expected, event.signature)

    def verify_connectivity(self) -> None:
        return None


class LiveHttpVoiceProvider(VoiceProvider):
    """Provider-neutral HTTP adapter; vendor-specific configuration stays outside CHIMERA."""

    name = "live"
    mode = "LIVE"

    def __init__(self, *, enabled: bool, base_url: str | None, api_key: str | None, agent_id: str | None, phone_number: str | None, timeout_seconds: float) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.agent_id = agent_id
        self.phone_number = phone_number
        self.timeout_seconds = timeout_seconds

    def _require_configuration(self) -> None:
        if not self.enabled:
            raise VoiceProviderError("voice_disabled")
        if not all((self.base_url, self.api_key, self.agent_id, self.phone_number)):
            raise VoiceProviderError("missing_configuration")

    def start_call(self, context: VoiceContext, *, idempotency_key: str, scenario: VoiceScenario) -> VoiceCallStartResult:
        self._require_configuration()
        body = json.dumps({
            "to": self.phone_number,
            "agent_id": self.agent_id,
            "idempotency_key": idempotency_key,
            "metadata": {
                "intervention_id": context.intervention_id,
                "recovery_case_id": context.recovery_case_id,
                "action": context.selected_action,
                "scenario": scenario.value,
            },
        }).encode("utf-8")
        request = Request(
            f"{self.base_url}/calls",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout):
            raise VoiceProviderError("provider_timeout") from None
        except (HTTPError, URLError, OSError, ValueError):
            raise VoiceProviderError("provider_unavailable") from None
        reference = data.get("call_id") or data.get("id") or data.get("reference")
        if not isinstance(reference, str) or not reference:
            raise VoiceProviderError("provider_invalid_response")
        return VoiceCallStartResult(provider=self.name, provider_call_reference=reference[:255])

    def verify_webhook(self, event: VoiceWebhookEvent) -> bool:
        if not self.api_key:
            return False
        expected = hmac.new(self.api_key.encode("utf-8"), canonical_webhook(event).encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, event.signature)

    def verify_connectivity(self) -> None:
        self._require_configuration()
        request = Request(
            f"{self.base_url}/health",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status >= 400:
                    raise VoiceProviderError("provider_unavailable")
                response.read(1)
        except VoiceProviderError:
            raise
        except (TimeoutError, socket.timeout):
            raise VoiceProviderError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise VoiceProviderError("invalid_credentials") from None
            raise VoiceProviderError("provider_unavailable") from None
        except (URLError, OSError):
            raise VoiceProviderError("provider_unavailable") from None


def canonical_webhook(event: VoiceWebhookEvent) -> str:
    return json.dumps({
        "event_id": event.event_id,
        "provider_call_reference": event.provider_call_reference,
        "event_type": event.event_type,
        "event_timestamp": event.event_timestamp.isoformat(),
    }, sort_keys=True, separators=(",", ":"))


def sign_webhook_event(event: VoiceWebhookEvent) -> str:
    return hashlib.sha256(canonical_webhook(event).encode("utf-8")).hexdigest()


def provider_from_settings(settings) -> VoiceProvider:
    provider_name = getattr(settings, "voice_provider", os.getenv("VOICE_PROVIDER", "local")).casefold()
    if provider_name == "live":
        return LiveHttpVoiceProvider(
            enabled=getattr(settings, "voice_enabled", False),
            base_url=getattr(settings, "voice_base_url", None),
            api_key=getattr(settings, "voice_api_key", None),
            agent_id=getattr(settings, "voice_agent_id", None),
            phone_number=getattr(settings, "voice_phone_number", None),
            timeout_seconds=getattr(settings, "voice_timeout_seconds", 10.0),
        )
    return LocalDeterministicVoiceProvider()
