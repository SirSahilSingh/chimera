from __future__ import annotations

import hashlib
import hmac
import base64
import json
import socket
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from backend.provider_modes import resolve_mode

from .context import MessagingContext
from .providers import MessageSendResult, MessagingProvider, MessagingProviderError


class TwilioMessagingProvider(MessagingProvider):
    name = "twilio"

    def __init__(self, account_sid: str | None, auth_token: str | None, from_number: str | None, to_number: str | None, *, enabled: bool, timeout_seconds: float = 10.0, base_url: str = "https://api.twilio.com/2010-04-01", content_sid: str | None = None, status_callback_url: str | None = None, whatsapp: bool = False, mode: str | None = None) -> None:
        self.account_sid, self.auth_token, self.from_number, self.to_number = account_sid, auth_token, from_number, to_number
        self.enabled, self.timeout_seconds, self.base_url = enabled, timeout_seconds, base_url.rstrip("/")
        self.content_sid = content_sid
        self.status_callback_url = status_callback_url
        self.whatsapp = whatsapp
        self.mode = resolve_mode(self.name, mode)

    def send_message(self, context: MessagingContext, content: str, idempotency_key: str) -> MessageSendResult:
        recipient = context.customer_phone or self.to_number
        if not self.enabled or not self.account_sid or not self.auth_token or not self.from_number or not recipient:
            raise MessagingProviderError("provider_not_configured", "Twilio messaging is missing a required setting.")
        if self.whatsapp and not self.content_sid:
            raise MessagingProviderError(
                "whatsapp_template_not_configured",
                "WhatsApp delivery needs an approved Twilio Content template SID.",
            )
        fields = {"To": self._address(recipient), "From": self._address(self.from_number)}
        if self.whatsapp and self.content_sid:
            fields["ContentSid"] = self.content_sid
            fields["ContentVariables"] = json.dumps({"1": content}, separators=(",", ":"))
        else:
            fields["Body"] = content
        if self.status_callback_url:
            fields["StatusCallback"] = self.status_callback_url
        body = urlencode(fields).encode()
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = Request(f"{self.base_url}/Accounts/{self.account_sid}/Messages.json", data=body, headers={"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode())
            provider_message_id = payload.get("sid")
            if not provider_message_id:
                raise MessagingProviderError(
                    "twilio_missing_message_id",
                    "Twilio accepted the request but did not return a message reference.",
                )
            return MessageSendResult(str(provider_message_id), "SENT", "QUEUED", datetime.now(timezone.utc))
        except MessagingProviderError:
            raise
        except HTTPError as exc:
            raise self._http_error(exc) from None
        except (TimeoutError, socket.timeout):
            raise MessagingProviderError("twilio_timeout", "Twilio did not respond before the delivery timeout.") from None
        except (URLError, OSError):
            raise MessagingProviderError("twilio_unavailable", "Twilio could not be reached for message delivery.") from None
        except (json.JSONDecodeError, KeyError, TypeError):
            raise MessagingProviderError("twilio_invalid_response", "Twilio returned an invalid message response.") from None
        except Exception as exc:
            raise MessagingProviderError("provider_request_failed", "Twilio message delivery failed.") from exc

    @staticmethod
    def _clean_provider_message(value: object) -> str:
        message = " ".join(str(value or "").split())
        return message[:240] or "Twilio rejected the message request."

    def _http_error(self, exc: HTTPError) -> MessagingProviderError:
        try:
            raw = exc.read(4096).decode("utf-8", errors="replace")
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        provider_code = payload.get("code")
        message = self._clean_provider_message(payload.get("message"))
        code = f"twilio_{provider_code}" if provider_code else f"twilio_http_{exc.code}"
        return MessagingProviderError(code, message, http_status=exc.code)

    def verify_connectivity(self) -> None:
        if not self.enabled or not self.account_sid or not self.auth_token or not self.from_number:
            raise RuntimeError("provider_not_configured")
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = Request(
            f"{self.base_url}/Accounts/{self.account_sid}.json",
            headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status >= 400:
                    raise RuntimeError("provider_unavailable")
                response.read(1)
        except RuntimeError:
            raise
        except (TimeoutError, socket.timeout):
            raise RuntimeError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("invalid_credentials") from None
            raise RuntimeError("provider_unavailable") from None
        except (URLError, OSError):
            raise RuntimeError("provider_unavailable") from None

    def _address(self, value: str) -> str:
        if not self.whatsapp:
            return value
        return value if value.casefold().startswith("whatsapp:") else f"whatsapp:{value}"

    def verify_webhook(self, raw_body: bytes, signature: str, webhook_url: str | None = None) -> bool:
        if not self.auth_token:
            return False
        if not webhook_url:
            return False
        params = sorted(parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True))
        message = webhook_url + "".join(key + value for key, value in params)
        expected = base64.b64encode(hmac.new(self.auth_token.encode(), message.encode(), hashlib.sha1).digest()).decode()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, raw_body: bytes, provider_event_id: str | None = None) -> dict:
        try:
            body = json.loads(raw_body.decode())
        except json.JSONDecodeError:
            body = dict(parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True))
        return {"provider_event_id": provider_event_id or f"twilio-event-{hashlib.sha256(raw_body).hexdigest()[:32]}", "provider_message_id": body.get("MessageSid") or body.get("SmsSid"), "event_type": body.get("MessageStatus", "delivery_update"), "delivery_state": body.get("MessageStatus", "unknown"), "occurred_at": datetime.now(timezone.utc)}
