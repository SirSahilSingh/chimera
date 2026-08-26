from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from ..context import PaymentContext
from ..errors import PaymentProviderError
from ..provider import PaymentLinkResult, PaymentProvider
from ..schemas import PaymentDemoScenario, PaymentStatus, PaymentWebhookEvent
from backend.provider_modes import ProviderMode


class LocalDeterministicPaymentProvider(PaymentProvider):
    name = "local"
    mode = ProviderMode.LOCAL.value

    def __init__(self, secret: str = "chimera-local-payment-secret") -> None:
        self.secret = secret
        self._contexts: dict[str, PaymentContext] = {}

    def create_payment_link(self, context: PaymentContext) -> PaymentLinkResult:
        self._contexts[context.idempotency_key] = context
        token = hashlib.sha256(f"local-payment-v1|{context.idempotency_key}".encode()).hexdigest()[:24]
        return PaymentLinkResult(f"local_plink_{token}", f"https://demo.chimera.local/payment/{token}", PaymentStatus.ACTIVE, context.expires_at)

    def get_payment_status(self, provider_payment_link_id: str) -> PaymentWebhookEvent:
        return self._event(provider_payment_link_id, PaymentDemoScenario.PAYMENT_PENDING)

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(self.secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def reconcile_payment(self, provider_payment_link_id: str) -> PaymentWebhookEvent:
        return self.get_payment_status(provider_payment_link_id)

    def expire_or_close_link(self, provider_payment_link_id: str) -> PaymentLinkResult:
        return PaymentLinkResult(provider_payment_link_id, f"https://demo.chimera.local/payment/closed/{provider_payment_link_id}", PaymentStatus.EXPIRED)

    def demo_event(self, provider_payment_link_id: str, scenario: PaymentDemoScenario) -> PaymentWebhookEvent:
        return self._event(provider_payment_link_id, scenario)

    def sign(self, event: PaymentWebhookEvent) -> str:
        return hmac.new(self.secret.encode(), event.model_dump_json().encode(), hashlib.sha256).hexdigest()

    def _event(self, provider_payment_link_id: str, scenario: PaymentDemoScenario) -> PaymentWebhookEvent:
        context = next((value for value in self._contexts.values() if value.idempotency_key and provider_payment_link_id.endswith(hashlib.sha256(f"local-payment-v1|{value.idempotency_key}".encode()).hexdigest()[:24])), None)
        amount = context.amount_paise if context else 0
        currency = context.currency if context else "INR"
        status = {
            PaymentDemoScenario.PAYMENT_SUCCESS: PaymentStatus.PAID,
            PaymentDemoScenario.PAYMENT_PENDING: PaymentStatus.ACTIVE,
            PaymentDemoScenario.PAYMENT_EXPIRED: PaymentStatus.EXPIRED,
            PaymentDemoScenario.PAYMENT_FAILED: PaymentStatus.FAILED,
            PaymentDemoScenario.DUPLICATE_WEBHOOK: PaymentStatus.PAID,
            PaymentDemoScenario.INVALID_WEBHOOK: PaymentStatus.PAID,
            PaymentDemoScenario.OUT_OF_ORDER_EVENT: PaymentStatus.PAID,
        }[scenario]
        event_type = {
            PaymentStatus.PAID: "payment_link.paid",
            PaymentStatus.ACTIVE: "payment_link.pending",
            PaymentStatus.EXPIRED: "payment_link.expired",
            PaymentStatus.FAILED: "payment_link.failed",
        }[status]
        token = hashlib.sha256(f"{provider_payment_link_id}|{scenario.value}".encode()).hexdigest()[:24]
        return PaymentWebhookEvent(provider_event_id=f"local-event-{token}", provider_payment_link_id=provider_payment_link_id, provider_payment_id=f"local_pay_{token}" if status == PaymentStatus.PAID else None, event_type=event_type, status=status, amount_paise=amount, currency=currency, occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=int(token[:6], 16) % 86400))


def _canonical(event: PaymentWebhookEvent) -> str:
    return json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
