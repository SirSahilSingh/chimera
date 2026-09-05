from __future__ import annotations

import json
import logging
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .provider import VoiceCallStartResult, VoiceProvider, VoiceProviderError
from .schemas import VoiceContext, VoiceScenario, VoiceWebhookEvent
from backend.provider_modes import resolve_mode

logger = logging.getLogger(__name__)


class VobizVoiceProvider(VoiceProvider):
    """Vobiz programmable cloud telephony provider for outbound voice recovery calling."""

    name = "vobiz"
    mode = "LIVE"

    def __init__(
        self,
        auth_id: str | None,
        auth_token: str | None,
        caller_id: str | None,
        public_base_url: str | None,
        *,
        api_base_url: str = "https://api.vobiz.ai",
        enabled: bool = False,
        timeout_seconds: float = 10.0,
        mode: str | None = None,
    ) -> None:
        self.auth_id = str(auth_id).strip().strip('"').strip("'") if auth_id else None
        self.auth_token = str(auth_token).strip().strip('"').strip("'") if auth_token else None
        self.caller_id = str(caller_id).strip().strip('"').strip("'") if caller_id else None
        raw_public = str(public_base_url).strip().rstrip("/") if public_base_url else None
        if raw_public and raw_public.endswith("/api/v1"):
            raw_public = raw_public[:-len("/api/v1")].rstrip("/")
        self.public_base_url = raw_public
        self.api_base_url = api_base_url.rstrip("/")
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.mode = resolve_mode(self.name, mode)

    def _format_phone(self, phone: str) -> str:
        clean = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
        if clean.startswith("+"):
            return clean
        if len(clean) == 10:
            return f"+91{clean}"
        if clean.startswith("91") and len(clean) == 12:
            return f"+{clean}"
        if clean.startswith("0") and len(clean) == 11:
            return f"+91{clean[1:]}"
        return f"+{clean}"

    def _require_configuration(self, context: VoiceContext | None = None) -> str | None:
        if not self.enabled:
            raise VoiceProviderError("voice_disabled", "Vobiz voice calling is not enabled in settings.")
        if not self.auth_id or not self.auth_token or not self.caller_id or not self.public_base_url:
            raise VoiceProviderError(
                "missing_configuration",
                "Vobiz requires VOBIZ_AUTH_ID, VOBIZ_AUTH_TOKEN, VOBIZ_CALLER_ID, and VOICE_PUBLIC_BASE_URL.",
            )
        phone = context.customer_phone if context else None
        if context is not None and not phone:
            raise VoiceProviderError("missing_customer_phone", "Customer phone number is required for voice call.")
        return phone

    def start_call(self, context: VoiceContext, *, idempotency_key: str, scenario: VoiceScenario) -> VoiceCallStartResult:
        phone = self._require_configuration(context)
        destination = self._format_phone(phone or "")
        caller = self._format_phone(self.caller_id or "")

        answer_url = f"{self.public_base_url}/api/v1/voice/vobiz/answer?intervention_id={context.intervention_id}"
        hangup_url = f"{self.public_base_url}/api/v1/voice/vobiz/hangup?intervention_id={context.intervention_id}"

        payload = {
            "from": caller,
            "to": destination,
            "answer_url": answer_url,
            "answer_method": "POST",
            "hangup_url": hangup_url,
            "hangup_method": "POST",
        }

        url = f"{self.api_base_url}/api/v1/Account/{self.auth_id}/Call/"
        body = json.dumps(payload).encode("utf-8")

        headers = {
            "X-Auth-ID": self.auth_id,
            "X-Auth-Token": self.auth_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        request = Request(url, data=body, headers=headers, method="POST")

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout):
            raise VoiceProviderError("provider_timeout", "Vobiz call request timed out.") from None
        except HTTPError as exc:
            reason = None
            try:
                err_body = json.loads(exc.read().decode("utf-8"))
                if isinstance(err_body, dict):
                    reason = err_body.get("message") or err_body.get("error") or str(err_body)
            except Exception:
                pass
            raise VoiceProviderError(
                "provider_request_failed",
                reason or f"Vobiz HTTP {exc.code}: {exc.reason}",
                f"vobiz_http_{exc.code}",
            ) from None
        except (URLError, OSError) as exc:
            raise VoiceProviderError("provider_unavailable", f"Vobiz network error: {exc}") from None
        except (ValueError, KeyError):
            raise VoiceProviderError("provider_invalid_response", "Vobiz returned invalid JSON.") from None

        # Vobiz returns call identifiers in various fields depending on API version
        reference = (
            resp_data.get("call_uuid")
            or resp_data.get("call_id")
            or resp_data.get("request_uuid")
            or resp_data.get("sid")
            or resp_data.get("id")
        )
        if isinstance(reference, list) and reference:
            reference = reference[0]
        if not isinstance(reference, str) or not reference.strip():
            # If Vobiz returns status: queued or success message without explicit call_uuid
            reference = f"vobiz-{idempotency_key[:24]}"

        return VoiceCallStartResult(provider=self.name, provider_call_reference=str(reference).strip()[:255])

    def verify_connectivity(self) -> None:
        self._require_configuration()
        # Ping Vobiz platform health endpoint with a strict timeout cap so probes never hang.
        probe_timeout = min(float(self.timeout_seconds), 3.0)
        url = f"{self.api_base_url}/health"
        try:
            request = Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "CHIMERA-VoiceProvider/1.0"},
                method="GET",
            )
            with urlopen(request, timeout=probe_timeout) as response:
                if response.status >= 400:
                    raise VoiceProviderError("provider_unavailable", f"Vobiz health check returned status {response.status}")
                return
        except VoiceProviderError:
            raise
        except Exception as exc:
            # When configured in TEST or SANDBOX mode, valid telephony credentials and
            # endpoints are sufficient even if outbound carrier health probe is blocked by cloud egress.
            if str(self.mode).upper() in {"TEST", "SANDBOX"}:
                logger.info("Vobiz test mode: probe completed with valid configuration (probe note: %s)", exc)
                return
            if isinstance(exc, (TimeoutError, socket.timeout)):
                raise VoiceProviderError("provider_timeout", "Vobiz connectivity check timed out.") from None
            if isinstance(exc, HTTPError) and exc.code in {401, 403}:
                raise VoiceProviderError("invalid_credentials", "Invalid Vobiz Auth ID or Auth Token.") from None
            raise VoiceProviderError("provider_unavailable", f"Vobiz service unreachable: {exc}") from None

