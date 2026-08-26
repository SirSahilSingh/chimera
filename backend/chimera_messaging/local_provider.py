from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from .context import MessagingContext
from .providers import MessageSendResult, MessagingProvider


class LocalDeterministicMessagingProvider(MessagingProvider):
    name = "local"
    mode = "LOCAL"

    def __init__(self, secret: str = "chimera-local-messaging-secret") -> None:
        self.secret = secret

    def send_message(self, context: MessagingContext, content: str, idempotency_key: str) -> MessageSendResult:
        reference = hashlib.sha256(f"local-message-v1|{idempotency_key}|{content}".encode()).hexdigest()[:24]
        return MessageSendResult(f"local_msg_{reference}", "SENT", "DELIVERED", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def verify_webhook(self, raw_body: bytes, signature: str, webhook_url: str | None = None) -> bool:
        expected = hmac.new(self.secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, raw_body: bytes, provider_event_id: str | None = None) -> dict:
        body = json.loads(raw_body.decode())
        occurred_at = body["occurred_at"]
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        return {"provider_event_id": provider_event_id or body["provider_event_id"], "provider_message_id": body["provider_message_id"], "event_type": body["event_type"], "delivery_state": body["delivery_state"], "occurred_at": occurred_at}

    def sign(self, raw_body: bytes) -> str:
        return hmac.new(self.secret.encode(), raw_body, hashlib.sha256).hexdigest()
