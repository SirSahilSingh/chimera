from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import AuditLog, PaymentOrder, PaymentOrderEvent
from backend.app.domain import CaseStatus
from backend.app.schemas import CaseCreate
from backend.app.services.case_service import CaseService
from backend.app.interventions.service import InterventionService

from .context import PaymentOrderContext
from .errors import PaymentNotFoundError, PaymentProviderError, PaymentValidationError, PaymentWebhookError
from .idempotency import sha256_json
from .provider import PaymentProvider
from .schemas import PaymentOrderCreate, PaymentStatus, PaymentWebhookEvent


class PaymentOrderService:
    """Own the initial checkout order and open recovery only after failure."""

    def __init__(self, session: Session, provider: PaymentProvider, *, case_service: CaseService, intervention_service: InterventionService, orchestrator) -> None:
        self.session = session
        self.provider = provider
        self.case_service = case_service
        self.interventions = intervention_service
        self.orchestrator = orchestrator

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def create_order(self, payload: PaymentOrderCreate) -> PaymentOrder:
        existing = self.session.scalar(
            select(PaymentOrder)
            .options(selectinload(PaymentOrder.events))
            .where(PaymentOrder.provider == self.provider.name, PaymentOrder.external_reference_id == payload.external_reference_id)
        )
        idempotency_key = hashlib.sha256(f"chimera-initial-order-v1|{self.provider.name}|{payload.external_reference_id}".encode()).hexdigest()
        request_payload = payload.model_dump(mode="json")
        request_hash = sha256_json(request_payload)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise PaymentValidationError("external_reference_id already exists with different order details")
            return self.get_order(existing.id)

        context = PaymentOrderContext(
            **request_payload,
            idempotency_key=idempotency_key,
        )
        result = self.provider.create_order(context)
        row = PaymentOrder(
            provider=self.provider.name,
            provider_mode=self.provider.mode,
            provider_order_id=result.provider_order_id,
            checkout_key_id=result.checkout_key_id,
            external_reference_id=context.external_reference_id,
            customer_id=context.customer_id,
            customer_phone=context.customer_phone,
            customer_email=context.customer_email,
            amount_paise=context.amount_paise,
            currency=context.currency,
            description=context.description,
            status=result.status.value,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            result_hash=sha256_json(result.raw or {"id": result.provider_order_id}),
        )
        self.session.add(row)
        self.session.flush()
        self.session.add(
            PaymentOrderEvent(
                payment_order_id=row.id,
                provider=self.provider.name,
                provider_mode=self.provider.mode,
                provider_event_id=f"created-order-{row.id}",
                event_type="order.created",
                status=row.status,
                provider_payment_id=None,
                amount_paise=row.amount_paise,
                currency=row.currency,
                signature_verified=False,
                source="system",
                occurred_at=self._now(),
                payload_hash=row.request_hash,
                payload_json={"provider_order_id": row.provider_order_id},
            )
        )
        self.session.commit()
        return self.get_order(row.id)

    def get_order(self, order_id: str) -> PaymentOrder:
        row = self.session.scalar(
            select(PaymentOrder)
            .options(selectinload(PaymentOrder.events))
            .where(PaymentOrder.id == order_id)
        )
        if row is None:
            raise PaymentNotFoundError("payment order not found")
        row.events.sort(key=lambda item: (item.occurred_at, item.id))
        return row

    def reconcile_order(self, order_id: str) -> PaymentOrder:
        row = self.get_order(order_id)
        event = self.provider.get_order_status(row.provider_order_id)
        return self._apply_event(event, source="reconciliation", signature_verified=True)

    def apply_webhook_event(self, event: PaymentWebhookEvent) -> PaymentOrder | None:
        if event.provider_order_id is None:
            return None
        row = self.session.scalar(
            select(PaymentOrder)
            .where(PaymentOrder.provider == self.provider.name, PaymentOrder.provider_order_id == event.provider_order_id)
        )
        if row is None:
            return None
        return self._apply_event(event, source="webhook", signature_verified=True)

    def _apply_event(self, event: PaymentWebhookEvent, *, source: str, signature_verified: bool) -> PaymentOrder:
        if event.provider_order_id is None:
            raise PaymentWebhookError("initial payment event has no order_id")
        row = self.session.scalar(
            select(PaymentOrder)
            .options(selectinload(PaymentOrder.events))
            .where(PaymentOrder.provider == self.provider.name, PaymentOrder.provider_order_id == event.provider_order_id)
        )
        if row is None:
            raise PaymentNotFoundError("payment order not found")
        duplicate = self.session.scalar(
            select(PaymentOrderEvent).where(
                PaymentOrderEvent.provider == self.provider.name,
                PaymentOrderEvent.provider_event_id == event.provider_event_id,
            )
        )
        if duplicate is not None:
            return self.get_order(row.id)
        amount = event.amount_paise or row.amount_paise
        if amount != row.amount_paise or event.currency != row.currency:
            raise PaymentValidationError("initial payment event amount or currency does not match order")
        target = event.status
        self.session.add(
            PaymentOrderEvent(
                payment_order_id=row.id,
                provider=self.provider.name,
                provider_mode=self.provider.mode,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                status=target.value,
                provider_payment_id=event.provider_payment_id,
                amount_paise=amount,
                currency=event.currency,
                signature_verified=signature_verified,
                source=source,
                occurred_at=event.occurred_at,
                payload_hash=sha256_json(event.model_dump(mode="json")),
                payload_json={
                    "provider_order_id": event.provider_order_id,
                    "provider_payment_id": event.provider_payment_id,
                    "provider_error_code": event.provider_error_code,
                    "provider_error_reason": event.provider_error_reason,
                    "status": target.value,
                },
            )
        )
        if target == PaymentStatus.PAID:
            row.status = target.value
            row.provider_payment_id = event.provider_payment_id or row.provider_payment_id
            self.session.commit()
            return self.get_order(row.id)
        if target == PaymentStatus.FAILED and row.status not in {PaymentStatus.PAID.value, PaymentStatus.FAILED.value}:
            row.status = target.value
            row.provider_payment_id = event.provider_payment_id or row.provider_payment_id
            row.failure_reason = failure_reason(event)
            self.session.commit()
            self._open_recovery(row, event)
        else:
            if row.status not in {PaymentStatus.PAID.value, PaymentStatus.FAILED.value}:
                row.status = target.value if target in {PaymentStatus.ACTIVE, PaymentStatus.FAILED} else row.status
            row.provider_payment_id = event.provider_payment_id or row.provider_payment_id
            self.session.commit()
        return self.get_order(row.id)

    def _open_recovery(self, order: PaymentOrder, event: PaymentWebhookEvent) -> None:
        if order.recovery_case_id:
            return
        external_event_id = f"{self.provider.name}:{event.provider_event_id}"
        case = self.case_service.create_case(
            CaseCreate(
                external_event_id=external_event_id,
                payment_id=event.provider_payment_id or order.provider_order_id,
                customer_id=order.customer_id,
                customer_phone=event.customer_phone or order.customer_phone,
                amount_paise=order.amount_paise,
                currency=order.currency,
                failure_reason=failure_reason(event),
                incident_flag=False,
                payment_method=payment_method(event),
                decision_timestamp=event.occurred_at,
            )
        )
        order.recovery_case_id = case.id
        self.session.add(
            AuditLog(
                recovery_case_id=case.id,
                event_type="INITIAL_PAYMENT_FAILED",
                actor="payment_order_service",
                payload_json={
                    "payment_order_id": order.id,
                    "provider_order_id": order.provider_order_id,
                    "provider_payment_id": event.provider_payment_id,
                    "failure_reason": failure_reason(event),
                },
            )
        )
        self.session.commit()
        decision = self.case_service.decide(case)
        intervention, _ = self.interventions.create_from_decision(decision.id)
        if intervention.action == "DO_NOTHING":
            return
        self.interventions.queue(intervention.id)
        try:
            self.orchestrator.route(intervention.id)
        except Exception as exc:
            self.session.add(
                AuditLog(
                    recovery_case_id=case.id,
                    decision_id=decision.id,
                    event_type="INITIAL_RECOVERY_ACTION_FAILED",
                    actor="payment_order_service",
                    payload_json={"action": intervention.action, "error": str(exc)[:255]},
                )
            )
            self.session.commit()


def failure_reason(event: PaymentWebhookEvent) -> str:
    text = f"{event.provider_error_code or ''} {event.provider_error_reason or ''}".casefold()
    if "insufficient" in text or "fund" in text:
        return "insufficient_funds"
    if "expire" in text or "card_expired" in text:
        return "expired_method"
    if any(token in text for token in ("timeout", "network", "technical", "server")):
        return "technical_degradation"
    if any(token in text for token in ("declin", "issuer", "authentication")):
        return "issuer_decline"
    return "other"


def payment_method(event: PaymentWebhookEvent) -> str:
    return {"upi": "upi", "netbanking": "netbanking", "card": "card"}.get((event.provider_payment_method or "").casefold(), "card")
