from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..context import PaymentContext
from ..errors import PaymentProviderError
from ..provider import PaymentLinkResult, PaymentProvider
from ..schemas import PaymentStatus, PaymentWebhookEvent
from backend.provider_modes import resolve_mode


class RazorpayPaymentProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self, key_id: str | None, key_secret: str | None, webhook_secret: str | None, *, enabled: bool, base_url: str = "https://api.razorpay.com/v1", timeout_seconds: float = 10.0, mode: str | None = None) -> None:
        self.key_id, self.key_secret, self.webhook_secret = key_id, key_secret, webhook_secret
        self.enabled, self.base_url, self.timeout_seconds = enabled, base_url.rstrip("/"), timeout_seconds
        self.mode = resolve_mode(self.name, mode)

    def _ensure_configured(self) -> None:
        if not self.enabled or not self.key_id or not self.key_secret:
            raise PaymentProviderError("provider_not_configured")

    def create_payment_link(self, context: PaymentContext) -> PaymentLinkResult:
        self._ensure_configured()
        body = {"amount": context.amount_paise, "currency": context.currency, "description": context.description, "reference_id": context.idempotency_key}
        if context.expires_at:
            body["expire_by"] = int(context.expires_at.timestamp())
        if context.customer_email or context.customer_phone:
            body["customer"] = {key: value for key, value in (("email", context.customer_email), ("contact", context.customer_phone)) if value}
        response = self._request("POST", "/payment_links", body)
        try:
            return PaymentLinkResult(response["id"], response["short_url"], PaymentStatus.ACTIVE, _timestamp(response.get("expire_by")), response)
        except (KeyError, TypeError) as exc:
            raise PaymentProviderError("provider_invalid_response") from exc

    def get_payment_status(self, provider_payment_link_id: str) -> PaymentWebhookEvent:
        self._ensure_configured()
        data = self._request("GET", f"/payment_links/{provider_payment_link_id}", None)
        status = _map_status(data.get("status"))
        return PaymentWebhookEvent(provider_event_id=f"reconcile-{provider_payment_link_id}-{status.value}", provider_payment_link_id=provider_payment_link_id, provider_payment_id=None, event_type="reconciliation", status=status, amount_paise=int(data.get("amount", 0)), currency=str(data.get("currency", "INR")), occurred_at=datetime.now(timezone.utc))

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return False
        expected = hmac.new(self.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, raw_body: bytes, provider_event_id: str | None = None) -> PaymentWebhookEvent:
        try:
            body = json.loads(raw_body.decode("utf-8"))
            event_name = str(body.get("event", "payment_link.pending"))
            payment_link = body.get("payload", {}).get("payment_link", {}).get("entity", {})
            payment = body.get("payload", {}).get("payment", {}).get("entity", {})
            link_id = str(payment_link.get("id") or payment.get("reference_id") or "")
            amount = int(payment_link.get("amount") or payment.get("amount") or 0)
            currency = str(payment_link.get("currency") or payment.get("currency") or "INR")
            return PaymentWebhookEvent(provider_event_id=provider_event_id or f"razorpay-event-{hashlib.sha256(raw_body).hexdigest()[:32]}", provider_payment_link_id=link_id, provider_payment_id=payment.get("id"), event_type=event_name, status=_event_status(event_name, payment_link.get("status")), amount_paise=amount, currency=currency, occurred_at=_timestamp(body.get("created_at")) or datetime.now(timezone.utc))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise PaymentProviderError("provider_invalid_webhook") from exc

    def reconcile_payment(self, provider_payment_link_id: str) -> PaymentWebhookEvent:
        return self.get_payment_status(provider_payment_link_id)

    def expire_or_close_link(self, provider_payment_link_id: str) -> PaymentLinkResult:
        self._ensure_configured()
        response = self._request("POST", f"/payment_links/{provider_payment_link_id}/cancel", {})
        return PaymentLinkResult(provider_payment_link_id, str(response.get("short_url", "")), PaymentStatus.CANCELLED, raw=response)

    def _request(self, method: str, path: str, body: dict | None) -> dict:
        token = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"})
        for attempt in range(2):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode())
            except (URLError, TimeoutError, OSError) as exc:
                if attempt == 1:
                    raise PaymentProviderError("provider_request_failed") from exc
            except (HTTPError, ValueError) as exc:
                raise PaymentProviderError("provider_request_failed") from exc
        raise PaymentProviderError("provider_request_failed")


def _timestamp(value):
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def _map_status(value: str | None) -> PaymentStatus:
    return {"issued": PaymentStatus.ACTIVE, "partially_paid": PaymentStatus.ACTIVE, "paid": PaymentStatus.PAID, "expired": PaymentStatus.EXPIRED, "cancelled": PaymentStatus.CANCELLED}.get(str(value).casefold(), PaymentStatus.FAILED)


def _event_status(event_name: str, provider_status: str | None) -> PaymentStatus:
    if event_name.endswith(".paid") or event_name == "payment.captured":
        return PaymentStatus.PAID
    if event_name.endswith(".expired"):
        return PaymentStatus.EXPIRED
    if event_name.endswith(".cancelled"):
        return PaymentStatus.CANCELLED
    if event_name.endswith(".failed"):
        return PaymentStatus.FAILED
    return _map_status(provider_status or "issued")
