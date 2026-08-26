from __future__ import annotations

from .schemas import PaymentWebhookEvent


def reconciliation_event(event: PaymentWebhookEvent) -> PaymentWebhookEvent:
    """Mark a provider's current status as an internal, auditable observation."""
    return event
