from __future__ import annotations

import hashlib
import hmac
import base64
import json
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen
from backend.provider_modes import resolve_mode

from .context import MessagingContext
from .providers import MessageSendResult, MessagingProvider


class TwilioMessagingProvider(MessagingProvider):
    name = "twilio"

    def __init__(self, account_sid: str | None, auth_token: str | None, from_number: str | None, to_number: str | None, *, enabled: bool, timeout_seconds: float = 10.0, base_url: str = "https://api.twilio.com/2010-04-01", mode: str | None = None) -> None:
        self.account_sid, self.auth_token, self.from_number, self.to_number = account_sid, auth_token, from_number, to_number
        self.enabled, self.timeout_seconds, self.base_url = enabled, timeout_seconds, base_url.rstrip("/")
        self.mode = resolve_mode(self.name, mode)

    def send_message(self, context: MessagingContext, content: str, idempotency_key: str) -> MessageSendResult:
        if not self.enabled or not self.account_sid or not self.auth_token or not self.from_number or not self.to_number:
            raise RuntimeError("provider_not_configured")
        body = urlencode({"To": self.to_number, "From": self.from_number, "Body": content}).encode()
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = Request(f"{self.base_url}/Accounts/{self.account_sid}/Messages.json", data=body, headers={"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            import json
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode())
            return MessageSendResult(str(payload["sid"]), "SENT", "QUEUED", datetime.now(timezone.utc))
        except Exception as exc:
            raise RuntimeError("provider_request_failed") from exc

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
