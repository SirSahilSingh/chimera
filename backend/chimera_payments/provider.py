from __future__ import annotations

from abc import ABC, abstractmethod

from .context import PaymentContext
from .errors import PaymentProviderError
from .schemas import PaymentStatus, PaymentWebhookEvent


class PaymentLinkResult:
    def __init__(self, provider_payment_link_id: str, short_url: str, status: PaymentStatus, expires_at=None, raw: dict | None = None) -> None:
        self.provider_payment_link_id = provider_payment_link_id
        self.short_url = short_url
        self.status = status
        self.expires_at = expires_at
        self.raw = raw or {}


class PaymentProvider(ABC):
    name: str
    mode: str = "LOCAL"

    @abstractmethod
    def create_payment_link(self, context: PaymentContext) -> PaymentLinkResult: ...

    @abstractmethod
    def get_payment_status(self, provider_payment_link_id: str) -> PaymentWebhookEvent: ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, signature: str) -> bool: ...

    def parse_webhook(self, raw_body: bytes, provider_event_id: str | None = None) -> PaymentWebhookEvent:
        event = PaymentWebhookEvent.model_validate_json(raw_body)
        return event.model_copy(update={"provider_event_id": provider_event_id} if provider_event_id else {})

    @abstractmethod
    def reconcile_payment(self, provider_payment_link_id: str) -> PaymentWebhookEvent: ...

    @abstractmethod
    def expire_or_close_link(self, provider_payment_link_id: str) -> PaymentLinkResult: ...

    def verify_connectivity(self) -> None:
        raise PaymentProviderError("unsupported_capability")
