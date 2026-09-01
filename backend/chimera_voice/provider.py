from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import base64
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from .context import context_hash
from .schemas import VoiceContext, VoiceScenario, VoiceWebhookEvent
from backend.provider_modes import resolve_mode


class VoiceProviderError(RuntimeError):
    def __init__(self, code: str, reason: str | None = None, provider_code: str | None = None) -> None:
        self.code = code
        self.reason = reason
        self.provider_code = provider_code
        super().__init__(reason or code)


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


class TwilioVoiceProvider(VoiceProvider):
    """Twilio trial voice adapter for the controlled CHIMERA call flow."""

    name = "twilio"
    mode = "LIVE"

    def __init__(self, account_sid: str | None, auth_token: str | None, from_number: str | None, public_base_url: str | None, *, enabled: bool, timeout_seconds: float = 10.0, language: str = "hi-IN", mode: str | None = None) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.language = language
        self.mode = resolve_mode(self.name, mode)

    def _require_configuration(self, context: VoiceContext | None = None) -> str | None:
        if not self.enabled:
            raise VoiceProviderError("voice_disabled")
        if not self.account_sid or not self.auth_token or not self.from_number or not self.public_base_url:
            raise VoiceProviderError("missing_configuration")
        phone = context.customer_phone if context else None
        if context is not None and not phone:
            raise VoiceProviderError("missing_customer_phone")
        return phone

    def start_call(self, context: VoiceContext, *, idempotency_key: str, scenario: VoiceScenario) -> VoiceCallStartResult:
        phone = self._require_configuration(context)
        callback = f"{self.public_base_url}/api/v1/voice/twilio/status?intervention_id={context.intervention_id}"
        twiml_url = f"{self.public_base_url}/api/v1/voice/twilio/twiml?intervention_id={context.intervention_id}"
        fields = {
            "To": phone,
            "From": self.from_number,
            "Url": twiml_url,
            "Method": "POST",
            "StatusCallback": callback,
            "StatusCallbackMethod": "POST",
            "StatusCallbackEvent": "initiated ringing answered completed",
            "MachineDetection": "Enable",
        }
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = Request(f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json", data=urlencode(fields).encode(), headers={"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded", "Idempotency-Key": idempotency_key}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            reference = str(payload["sid"])
        except (TimeoutError, socket.timeout):
            raise VoiceProviderError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise VoiceProviderError("invalid_credentials") from None
            raise self._request_error(exc) from None
        except (URLError, OSError):
            raise VoiceProviderError("provider_request_failed") from None
        except (ValueError, KeyError):
            raise VoiceProviderError("provider_request_failed", "Twilio returned an invalid call response.") from None
        return VoiceCallStartResult(provider=self.name, provider_call_reference=reference[:255])

    @staticmethod
    def _request_error(exc: HTTPError) -> VoiceProviderError:
        """Keep Twilio's safe diagnostic without persisting credentials or request data."""
        reason = None
        provider_code = None
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, ValueError):
            payload = {}
        if isinstance(payload, dict):
            raw_code = payload.get("code")
            if isinstance(raw_code, (int, str)) and str(raw_code).isdigit():
                provider_code = f"twilio_{str(raw_code)}"
            raw_message = payload.get("message")
            if isinstance(raw_message, str) and raw_message.strip():
                reason = raw_message.strip()[:255]
        return VoiceProviderError("provider_request_failed", reason, provider_code or f"twilio_http_{exc.code}")

    def verify_connectivity(self) -> None:
        self._require_configuration()
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = Request(f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}.json", headers={"Authorization": f"Basic {token}", "Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status >= 400:
                    raise VoiceProviderError("provider_unavailable")
                response.read(1)
        except VoiceProviderError:
            raise
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise VoiceProviderError("invalid_credentials") from None
            raise VoiceProviderError("provider_unavailable") from None
        except (TimeoutError, socket.timeout):
            raise VoiceProviderError("provider_timeout") from None
        except (URLError, OSError):
            raise VoiceProviderError("provider_unavailable") from None

    def fetch_recording(self, recording_url: str) -> bytes:
        """Fetch a Twilio recording for server-side transcription."""
        if not self.account_sid or not self.auth_token:
            raise VoiceProviderError("missing_configuration")
        url = recording_url if recording_url.endswith((".wav", ".mp3")) else f"{recording_url}.wav"
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = Request(url, headers={"Authorization": f"Basic {token}", "Accept": "audio/wav"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                audio = response.read()
        except (TimeoutError, socket.timeout):
            raise VoiceProviderError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise VoiceProviderError("invalid_credentials") from None
            raise VoiceProviderError("provider_request_failed") from None
        except (URLError, OSError):
            raise VoiceProviderError("provider_unavailable") from None
        if not audio:
            raise VoiceProviderError("empty_recording")
        return audio

    def verify_twilio_request(self, url: str, fields: dict[str, str], signature: str) -> bool:
        if not self.auth_token or not signature:
            return False
        message = url + "".join(key + fields[key] for key in sorted(fields))
        expected = base64.b64encode(hmac.new(self.auth_token.encode(), message.encode(), hashlib.sha1).digest()).decode()
        return hmac.compare_digest(expected, signature)


class ExotelVoiceProvider(VoiceProvider):
    """Exotel outbound-call adapter using a configured Exotel call flow."""

    name = "exotel"
    mode = "LIVE"

    def __init__(
        self,
        api_key: str | None,
        api_token: str | None,
        account_sid: str | None,
        flow_url: str | None,
        caller_id: str | None,
        api_base_url: str,
        public_base_url: str | None,
        webhook_secret: str | None,
        *,
        enabled: bool,
        timeout_seconds: float = 10.0,
        agentstream_enabled: bool = False,
        stream_url: str | None = None,
        mode: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_token = api_token
        self.account_sid = account_sid
        self.flow_url = flow_url
        self.caller_id = caller_id
        self.api_base_url = api_base_url.rstrip("/")
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.webhook_secret = webhook_secret
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.agentstream_enabled = agentstream_enabled
        self.stream_url = stream_url.rstrip("/") if stream_url else None
        self.mode = resolve_mode(self.name, mode)

    def _require_configuration(self, context: VoiceContext | None = None) -> str | None:
        if not self.enabled:
            raise VoiceProviderError("voice_disabled")
        required = (self.api_key, self.api_token, self.account_sid, self.caller_id, self.public_base_url)
        if not all(required) or (not self.agentstream_enabled and not self.flow_url) or (self.agentstream_enabled and not self.stream_url):
            raise VoiceProviderError("missing_configuration")
        phone = context.customer_phone if context else None
        if context is not None and not phone:
            raise VoiceProviderError("missing_customer_phone")
        return phone

    def start_call(self, context: VoiceContext, *, idempotency_key: str, scenario: VoiceScenario) -> VoiceCallStartResult:
        phone = self._require_configuration(context)
        callback = f"{self.public_base_url}/api/v1/voice/exotel/status"
        if self.webhook_secret:
            callback = f"{callback}?{urlencode({'token': self.webhook_secret})}"
        custom_field = f"{context.intervention_id}|{idempotency_key}|{scenario.value}"
        if self.agentstream_enabled:
            stream_url = f"{self.stream_url}?{urlencode({'intervention_id': context.intervention_id})}"
            fields = [
                ("from", self._format_e164(phone or "")),
                ("callerid", self.caller_id or ""),
                ("streamurl", stream_url),
                ("streamtype", "bidirectional"),
                ("record", "true"),
                ("statuscallback", callback),
                ("statuscallbackevents[]", "ringing"),
                ("statuscallbackevents[]", "terminal"),
                ("customfield", custom_field),
            ]
        else:
            fields = {
                "From": self._format_destination(phone or ""),
                "CallerId": self.caller_id or "",
                "CallType": "trans",
                "Url": self.flow_url or "",
                "StatusCallback": callback,
                "CustomField": custom_field,
            }
        token = base64.b64encode(f"{self.api_key}:{self.api_token}".encode()).decode()

        def post_call(request_fields: list[tuple[str, str]] | dict[str, str]) -> str:
            request = Request(
                f"{self.api_base_url}/v1/Accounts/{self.account_sid}/calls/connect",
                data=urlencode(request_fields, doseq=True).encode(),
                headers={"Authorization": f"Basic {token}", "Accept": "application/json, application/xml", "Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return response.read().decode("utf-8")
            except (TimeoutError, socket.timeout):
                raise VoiceProviderError("provider_timeout") from None
            except HTTPError as exc:
                raise self._request_error(exc) from None
            except (URLError, OSError):
                raise VoiceProviderError("provider_request_failed") from None

        try:
            payload = post_call(fields)
        except VoiceProviderError as error:
            # Some India-hosted Exotel accounts still validate the AgentStream
            # destination using the legacy national format, even though the
            # AgentStream documentation specifies E.164. Retry only this
            # explicit validation error; never retry timeouts or unknown 4xx/5xx
            # responses, and never retry after a successful provider response.
            if not (
                self.agentstream_enabled
                and error.provider_code == "exotel_http_400"
                and error.reason
                and "invalid 'from' specified" in error.reason.casefold()
                and self._format_destination(phone or "") != self._format_e164(phone or "")
            ):
                raise
            fallback_fields = list(fields)
            fallback_fields[0] = ("from", self._format_destination(phone or ""))
            payload = post_call(fallback_fields)

        try:
            reference = self._extract_call_reference(payload)
        except (ET.ParseError, ValueError):
            raise VoiceProviderError("provider_invalid_response") from None
        if not reference:
            raise VoiceProviderError("provider_invalid_response", "Exotel returned a successful response without a call SID.")
        return VoiceCallStartResult(provider=self.name, provider_call_reference=reference[:255])

    @staticmethod
    def _format_destination(phone: str) -> str:
        """Exotel's legacy Connect API expects Indian mobile numbers with a leading zero."""
        compact = phone.replace(" ", "").replace("-", "")
        if compact.startswith("+91") and len(compact) == 13:
            return f"0{compact[3:]}"
        if compact.startswith("91") and len(compact) == 12:
            return f"0{compact[2:]}"
        if len(compact) == 10 and compact.isdigit():
            return f"0{compact}"
        return compact

    @staticmethod
    def _format_e164(phone: str) -> str:
        compact = phone.replace(" ", "").replace("-", "")
        if compact.startswith("0") and len(compact) == 11:
            return f"+91{compact[1:]}"
        if compact.startswith("91") and len(compact) == 12:
            return f"+{compact}"
        if compact.startswith("+"):
            return compact
        if len(compact) == 10 and compact.isdigit():
            return f"+91{compact}"
        return compact

    @staticmethod
    def _extract_call_reference(payload: str) -> str | None:
        try:
            parsed = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            candidates: list[Any] = [parsed]
            while candidates:
                value = candidates.pop()
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key.casefold() in {"sid", "callsid", "call_sid"} and isinstance(child, str) and child:
                            return child
                        if isinstance(child, (dict, list)):
                            candidates.append(child)
                elif isinstance(value, list):
                    candidates.extend(value)
            return None
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return None
        return next((element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1].casefold() in {"sid", "callsid"} and element.text), None)

    def verify_webhook(self, event: VoiceWebhookEvent) -> bool:
        if not self.webhook_secret:
            return True
        expected = hmac.new(self.webhook_secret.encode(), canonical_webhook(event).encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, event.signature)

    def verify_connectivity(self) -> None:
        self._require_configuration()
        token = base64.b64encode(f"{self.api_key}:{self.api_token}".encode()).decode()
        request = Request(
            f"{self.api_base_url}/v1/Accounts/{self.account_sid}/Calls.json?PageSize=1",
            headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
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
            raise self._request_error(exc) from None
        except (URLError, OSError):
            raise VoiceProviderError("provider_unavailable") from None

    def sign_callback_event(self, event: VoiceWebhookEvent) -> str:
        if not self.webhook_secret:
            return "exotel-callback"
        return hmac.new(self.webhook_secret.encode(), canonical_webhook(event).encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _request_error(exc: HTTPError) -> VoiceProviderError:
        try:
            body = exc.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = None
            message = None
            if isinstance(parsed, dict):
                values: list[Any] = [parsed]
                while values and message is None:
                    value = values.pop()
                    if isinstance(value, dict):
                        for key, child in value.items():
                            if key.casefold() in {"message", "error_message", "error_description"} and isinstance(child, str) and child.strip():
                                message = child.strip()
                                break
                            if isinstance(child, (dict, list)):
                                values.append(child)
                    elif isinstance(value, list):
                        values.extend(value)
            if message is None:
                root = ET.fromstring(body)
                message = next((element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1].casefold() == "message" and element.text), None)
            if message is None and body.strip():
                message = body.strip()
        except (AttributeError, UnicodeDecodeError, ET.ParseError, ValueError):
            message = None
        return VoiceProviderError("provider_request_failed", message[:255] if message else None, f"exotel_http_{exc.code}")


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
    if provider_name == "exotel":
        return ExotelVoiceProvider(
            getattr(settings, "exotel_api_key", None),
            getattr(settings, "exotel_api_token", None),
            getattr(settings, "exotel_account_sid", None),
            getattr(settings, "exotel_flow_url", None),
            getattr(settings, "exotel_caller_id", None),
            getattr(settings, "exotel_api_base_url", "https://api.in.exotel.com"),
            getattr(settings, "voice_public_base_url", None),
            getattr(settings, "exotel_webhook_secret", None),
            enabled=getattr(settings, "voice_enabled", False),
            timeout_seconds=getattr(settings, "voice_timeout_seconds", 10.0),
            agentstream_enabled=getattr(settings, "exotel_agentstream_enabled", False),
            stream_url=getattr(settings, "exotel_stream_url", None),
            mode=getattr(settings, "voice_mode", None),
        )
    if provider_name == "twilio":
        return TwilioVoiceProvider(
            getattr(settings, "twilio_account_sid", None),
            getattr(settings, "twilio_auth_token", None),
            getattr(settings, "voice_phone_number", None),
            getattr(settings, "voice_public_base_url", None),
            enabled=getattr(settings, "voice_enabled", False),
            timeout_seconds=getattr(settings, "voice_timeout_seconds", 10.0),
            language=getattr(settings, "voice_language", "hi-IN"),
            mode=getattr(settings, "voice_mode", None),
        )
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
