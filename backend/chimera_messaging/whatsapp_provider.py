from __future__ import annotations

import hashlib
import hmac
import json
import socket
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.provider_modes import resolve_mode

from .context import MessagingContext
from .providers import MessageSendResult, MessagingProvider


class WhatsAppMessagingProvider(MessagingProvider):
    """Meta WhatsApp Cloud API adapter.

    The adapter deliberately sends a single text message or an approved
    template. It does not send credentials or decision metadata to Meta.
    WhatsApp's test number is suitable for buildathon demos; production use
    still requires the recipient opt-in/template rules imposed by Meta.
    """

    name = "whatsapp"

    def __init__(
        self,
        access_token: str | None,
        phone_number_id: str | None,
        fallback_to_number: str | None,
        verify_token: str | None,
        app_secret: str | None,
        *,
        enabled: bool,
        timeout_seconds: float = 10.0,
        api_version: str = "v23.0",
        template_name: str | None = None,
        template_language: str = "en_US",
        mode: str | None = None,
    ) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.fallback_to_number = fallback_to_number
        self.verify_token = verify_token
        self.app_secret = app_secret
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.api_version = api_version.strip("/")
        self.template_name = template_name
        self.template_language = template_language
        self.mode = resolve_mode(self.name, mode)

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    def _require_configuration(self, *, require_recipient: bool = False, context: MessagingContext | None = None) -> str | None:
        if not self.enabled or not self.access_token or not self.phone_number_id:
            raise RuntimeError("provider_not_configured")
        recipient = (context.customer_phone if context else None) or self.fallback_to_number
        if require_recipient and not recipient:
            raise RuntimeError("missing_customer_phone")
        return recipient

    def send_message(self, context: MessagingContext, content: str, idempotency_key: str) -> MessageSendResult:
        recipient = self._require_configuration(require_recipient=True, context=context)
        if self.template_name:
            message = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": self.template_name,
                    "language": {"code": self.template_language},
                    "components": [{"type": "body", "parameters": [{"type": "text", "text": content}]}],
                },
            }
        else:
            message = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"preview_url": True, "body": content},
            }
        response = self._request("POST", f"/{self.phone_number_id}/messages", message, idempotency_key=idempotency_key)
        try:
            provider_id = str(response["messages"][0]["id"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("provider_invalid_response") from exc
        return MessageSendResult(provider_message_id=provider_id[:255], status="SENT", delivery_state="QUEUED", sent_at=datetime.now(timezone.utc))

    def verify_connectivity(self) -> None:
        self._require_configuration()
        self._request("GET", f"/{self.phone_number_id}?fields=id,display_phone_number", None)

    def verify_webhook(self, raw_body: bytes, signature: str, webhook_url: str | None = None) -> bool:
        del webhook_url
        if not self.app_secret or not signature:
            return False
        normalized = signature.removeprefix("sha256=")
        expected = hmac.new(self.app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, normalized)

    def verify_challenge(self, mode: str, token: str, challenge: str) -> str | None:
        if mode == "subscribe" and self.verify_token and hmac.compare_digest(token, self.verify_token):
            return challenge
        return None

    def parse_webhook(self, raw_body: bytes, provider_event_id: str | None = None) -> dict:
        try:
            body = json.loads(raw_body.decode("utf-8"))
            value = body["entry"][0]["changes"][0]["value"]
            messages = value.get("messages") or []
            statuses = value.get("statuses") or []
            message = messages[0] if messages else None
            status = statuses[0] if statuses else None
            item = message or status
            if not item:
                raise ValueError("webhook has no message or status")
            provider_message_id = item.get("id")
            state = str(status.get("status") if status else "received").upper()
            return {
                "provider_event_id": provider_event_id or f"whatsapp-event-{hashlib.sha256(raw_body).hexdigest()[:32]}",
                "provider_message_id": provider_message_id,
                "event_type": f"message.{state.casefold()}",
                "delivery_state": state,
                "occurred_at": datetime.now(timezone.utc),
            }
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("invalid_whatsapp_webhook") from exc

    def _request(self, method: str, path: str, body: dict | None, *, idempotency_key: str | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["X-CHIMERA-IDEMPOTENCY-KEY"] = idempotency_key
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout):
            raise RuntimeError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("invalid_credentials") from None
            raise RuntimeError("provider_request_failed") from None
        except (URLError, OSError, ValueError):
            raise RuntimeError("provider_request_failed") from None
