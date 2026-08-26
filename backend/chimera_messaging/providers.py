from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .context import MessagingContext


@dataclass(frozen=True)
class MessageSendResult:
    provider_message_id: str
    status: str
    delivery_state: str
    sent_at: object


class MessagingProvider(ABC):
    name: str

    @abstractmethod
    def send_message(self, context: MessagingContext, content: str, idempotency_key: str) -> MessageSendResult: ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, signature: str, webhook_url: str | None = None) -> bool: ...

    @abstractmethod
    def parse_webhook(self, raw_body: bytes, provider_event_id: str | None = None) -> dict: ...
