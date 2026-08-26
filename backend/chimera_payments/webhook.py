from __future__ import annotations

import json

from .errors import PaymentWebhookError
from .schemas import PaymentWebhookEvent


def parse_webhook(raw_body: bytes) -> PaymentWebhookEvent:
    try:
        return PaymentWebhookEvent.model_validate_json(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PaymentWebhookError("invalid_webhook_payload") from exc
