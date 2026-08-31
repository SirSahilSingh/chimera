from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.db.models import AuditLog, Intervention, PaymentAttempt, PaymentEvent, PaymentLink, RecoveryCase
from backend.app.interventions.service import InterventionService
from backend.app.interventions.state_machine import InterventionStatus
from backend.app.schemas import InterventionOutcomeCreate

from .context import PaymentContext
from .errors import PaymentAuthorityError, PaymentNotFoundError, PaymentProviderError, PaymentValidationError, PaymentWebhookError
from .idempotency import payment_idempotency_key, sha256_json
from .provider import PaymentProvider
from .providers.local import LocalDeterministicPaymentProvider
from .schemas import PaymentDemoScenario, PaymentLinkResponse, PaymentStatus, PaymentWebhookEvent
from .validation import validate_payment_context, validate_provider_amount_currency
from .webhook import parse_webhook
from .versions import PAYMENT_VERSION


class PaymentService:
    """Single authority for link creation, provider confirmation and recovery accounting."""

    def __init__(self, session: Session, provider: PaymentProvider, *, demo_enabled: bool = True, enabled: bool = True, intervention_service: InterventionService | None = None) -> None:
        self.session = session
        self.provider = provider
        self.demo_enabled = demo_enabled
        self.enabled = enabled
        self.interventions = intervention_service or InterventionService(session)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _timestamp(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def create_payment_link(self, intervention_id: str) -> PaymentLink:
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "PAYMENT_LINK" or intervention.decision.selected_action != "PAYMENT_LINK":
            raise PaymentAuthorityError("payment link creation is only allowed for PAYMENT_LINK")
        return self._create_for_intervention(intervention)

    def create_for_voice_intent(self, intervention_id: str, intent: str) -> PaymentLink:
        if intent != "SEND_PAYMENT_LINK":
            raise PaymentAuthorityError("voice payment link requires validated SEND_PAYMENT_LINK intent")
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "VOICE_RECOVERY" or intervention.decision.selected_action != "VOICE_RECOVERY":
            raise PaymentAuthorityError("voice payment link requires VOICE_RECOVERY")
        return self._create_for_intervention(intervention)

    def create_for_message(self, intervention_id: str) -> PaymentLink:
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "SEND_MESSAGE" or intervention.decision.selected_action != "SEND_MESSAGE":
            raise PaymentAuthorityError("message payment link requires SEND_MESSAGE")
        return self._create_for_intervention(intervention, allow_refresh=True)

    def get_payment(self, payment_id: str) -> PaymentLink:
        row = self.session.scalar(select(PaymentLink).options(selectinload(PaymentLink.attempts), selectinload(PaymentLink.events)).where(PaymentLink.id == payment_id))
        if row is None:
            raise PaymentNotFoundError("payment not found")
        row.attempts.sort(key=lambda value: (self._timestamp(value.first_seen_at), value.id))
        row.events.sort(key=lambda value: (self._timestamp(value.occurred_at), value.id))
        return row

    def list_for_intervention(self, intervention_id: str) -> list[PaymentLink]:
        self.interventions.get_intervention(intervention_id)
        return list(self.session.scalars(select(PaymentLink).options(selectinload(PaymentLink.attempts), selectinload(PaymentLink.events)).where(PaymentLink.intervention_id == intervention_id).order_by(PaymentLink.created_at.asc(), PaymentLink.id.asc())))

    def process_webhook(self, provider_name: str, raw_body: bytes, signature: str, provider_event_id: str | None = None) -> PaymentLink:
        if self.provider.name != provider_name or not self.provider.verify_webhook(raw_body, signature):
            raise PaymentWebhookError("invalid_webhook_signature")
        try:
            event = self.provider.parse_webhook(raw_body, provider_event_id)
        except PaymentProviderError as exc:
            raise PaymentWebhookError(exc.code) from exc
        return self._apply_event(provider_name, event, source="webhook", signature_verified=True)

    def reconcile_payment(self, payment_id: str) -> PaymentLink:
        link = self.get_payment(payment_id)
        event = self.provider.reconcile_payment(link.provider_payment_link_id)
        event = event.model_copy(update={"provider_payment_link_id": link.provider_payment_link_id})
        return self._apply_event(self.provider.name, event, source="reconciliation", signature_verified=True)

    def demo_complete(self, payment_id: str, scenario: PaymentDemoScenario) -> PaymentLink:
        if not self.demo_enabled or self.provider.name != "local" or not isinstance(self.provider, LocalDeterministicPaymentProvider):
            raise PaymentAuthorityError("local payment demo is disabled")
        link = self.get_payment(payment_id)
        if scenario == PaymentDemoScenario.INVALID_WEBHOOK:
            event = self.provider.demo_event(link.provider_payment_link_id, PaymentDemoScenario.PAYMENT_SUCCESS)
            raw = event.model_dump_json().encode()
            return self.process_webhook("local", raw, "invalid")
        if scenario == PaymentDemoScenario.OUT_OF_ORDER_EVENT:
            pending = self.provider.demo_event(link.provider_payment_link_id, PaymentDemoScenario.PAYMENT_PENDING)
            self._apply_event("local", pending, source="webhook", signature_verified=True)
            success = self.provider.demo_event(link.provider_payment_link_id, PaymentDemoScenario.PAYMENT_SUCCESS)
            result = self._apply_event("local", success, source="webhook", signature_verified=True)
            stale = pending.model_copy(update={"provider_event_id": pending.provider_event_id + "-stale"})
            self._apply_event("local", stale, source="webhook", signature_verified=True)
            return result
        event = self.provider.demo_event(link.provider_payment_link_id, scenario)
        raw = event.model_dump_json().encode()
        signed = self.provider.sign(event)
        result = self.process_webhook("local", raw, signed)
        if scenario == PaymentDemoScenario.DUPLICATE_WEBHOOK:
            self.process_webhook("local", raw, signed)
        return result

    def expire_or_close_link(self, payment_id: str) -> PaymentLink:
        link = self.get_payment(payment_id)
        result = self.provider.expire_or_close_link(link.provider_payment_link_id)
        event = PaymentWebhookEvent(provider_event_id=f"close-{link.id}", provider_payment_link_id=link.provider_payment_link_id, event_type="payment_link.expired", status=PaymentStatus.EXPIRED, amount_paise=link.amount_paise, currency=link.currency, occurred_at=self._now())
        return self._apply_event(self.provider.name, event, source="reconciliation", signature_verified=True)

    def _create_for_intervention(self, intervention: Intervention, *, allow_refresh: bool = False) -> PaymentLink:
        if not self.enabled:
            raise PaymentAuthorityError("payments_disabled")
        if intervention.status == InterventionStatus.READY.value:
            self.interventions.execute(intervention.id)
            intervention = self.interventions.get_intervention(intervention.id)
        if intervention.status != InterventionStatus.AWAITING_OUTCOME.value:
            raise PaymentAuthorityError(f"payment link requires executable intervention, got {intervention.status}")
        existing = self.session.scalar(select(PaymentLink).where(PaymentLink.intervention_id == intervention.id))
        if existing is not None and (not allow_refresh or existing.status in {PaymentStatus.ACTIVE.value, PaymentStatus.PAID.value}):
            return self.get_payment(existing.id)
        refresh_suffix = "initial" if existing is None else f"refresh-{len(self.list_for_intervention(intervention.id))}"
        key = payment_idempotency_key(intervention.id, intervention.decision_id, f"{self.provider.name}|{refresh_suffix}")
        context = validate_payment_context(PaymentContext(
            recovery_case_id=intervention.recovery_case_id,
            intervention_id=intervention.id,
            decision_id=intervention.decision_id,
            amount_paise=intervention.recovery_case.amount_paise,
            currency=intervention.recovery_case.currency,
            description=f"CHIMERA recovery {intervention.recovery_case.payment_id}",
            customer_phone=intervention.recovery_case.customer_phone,
            idempotency_key=key,
        ))
        request_hash = sha256_json(context.model_dump(mode="json"))
        try:
            result = self.provider.create_payment_link(context)
            row = PaymentLink(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, provider=self.provider.name, provider_mode=self.provider.mode, provider_payment_link_id=result.provider_payment_link_id, short_url=result.short_url, amount_paise=context.amount_paise, currency=context.currency, status=result.status.value, idempotency_key=key, request_hash=request_hash, result_hash=sha256_json(result.raw or {"id": result.provider_payment_link_id, "short_url": result.short_url, "status": result.status.value}), expires_at=result.expires_at)
            self.session.add(row)
            self.session.flush()
            self.session.add(PaymentEvent(payment_link_id=row.id, provider=self.provider.name, provider_mode=self.provider.mode, provider_event_id=f"created-{row.id}", event_type="payment_link.created", status=row.status, amount_paise=row.amount_paise, currency=row.currency, signature_verified=False, source="system", occurred_at=self._now(), payload_hash=request_hash, payload_json={"provider_payment_link_id": row.provider_payment_link_id}))
            self.session.add(AuditLog(recovery_case_id=row.recovery_case_id, decision_id=row.decision_id, event_type="PAYMENT_LINK_CREATED", actor="payment_service", payload_json={"payment_id": row.id, "provider": row.provider, "status": row.status}))
            self.session.commit()
            return self.get_payment(row.id)
        except PaymentProviderError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.session.scalar(select(PaymentLink).where(PaymentLink.idempotency_key == key))
            if existing is not None:
                return self.get_payment(existing.id)
            raise PaymentValidationError("payment link could not be persisted") from exc

    def _apply_event(self, provider_name: str, event: PaymentWebhookEvent, *, source: str, signature_verified: bool) -> PaymentLink:
        if provider_name != self.provider.name:
            raise PaymentWebhookError("provider is not configured for this boundary")
        link = self.session.scalar(select(PaymentLink).where(PaymentLink.provider == provider_name, PaymentLink.provider_payment_link_id == event.provider_payment_link_id))
        if link is None:
            raise PaymentNotFoundError("payment link not found for provider reference")
        case = self.session.get(RecoveryCase, link.recovery_case_id)
        if case is not None and event.customer_phone and not case.customer_phone:
            case.customer_phone = event.customer_phone[:32]
        existing = self.session.scalar(select(PaymentEvent).where(PaymentEvent.provider == provider_name, PaymentEvent.provider_event_id == event.provider_event_id))
        if existing is not None:
            return self.get_payment(link.id)
        validate_provider_amount_currency(event.amount_paise, event.currency, link.amount_paise, link.currency)
        existing_attempt = self.session.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_link_id == link.id).order_by(PaymentAttempt.last_seen_at.desc(), PaymentAttempt.id.desc()))
        if link.status in {PaymentStatus.PAID.value, PaymentStatus.EXPIRED.value, PaymentStatus.CANCELLED.value, PaymentStatus.FAILED.value}:
            self.session.add(PaymentEvent(payment_link_id=link.id, payment_attempt_id=existing_attempt.id if existing_attempt else None, provider=provider_name, provider_mode=self.provider.mode, provider_event_id=event.provider_event_id, event_type=event.event_type, status=event.status.value, amount_paise=event.amount_paise, currency=event.currency, signature_verified=signature_verified, source=source, occurred_at=event.occurred_at, payload_hash=sha256_json(event.model_dump(mode="json")), payload_json={"provider_event_id": event.provider_event_id, "provider_payment_link_id": event.provider_payment_link_id, "provider_payment_id": event.provider_payment_id, "status": event.status.value, "processing_result": "ignored_terminal_state"}))
            self.session.commit()
            return self.get_payment(link.id)
        target = event.status
        attempt = existing_attempt
        if attempt is None:
            attempt = PaymentAttempt(payment_link_id=link.id, provider_payment_id=event.provider_payment_id, amount_paise=event.amount_paise, currency=event.currency, status=target.value)
            self.session.add(attempt)
            self.session.flush()
        else:
            attempt.provider_payment_id = attempt.provider_payment_id or event.provider_payment_id
            attempt.status = target.value
            attempt.last_seen_at = self._now()
        event_row = PaymentEvent(payment_link_id=link.id, payment_attempt_id=attempt.id, provider=provider_name, provider_mode=self.provider.mode, provider_event_id=event.provider_event_id, event_type=event.event_type, status=target.value, amount_paise=event.amount_paise, currency=event.currency, signature_verified=signature_verified, source=source, occurred_at=event.occurred_at, payload_hash=sha256_json(event.model_dump(mode="json")), payload_json={"provider_event_id": event.provider_event_id, "provider_payment_link_id": event.provider_payment_link_id, "provider_payment_id": event.provider_payment_id, "status": target.value, "processing_result": "applied"})
        self.session.add(event_row)
        if link.status == PaymentStatus.PAID.value:
            self.session.commit()
            return self.get_payment(link.id)
        if target == PaymentStatus.PAID:
            link.status = target.value
            self._record_recovery(link, event)
        elif link.status not in {PaymentStatus.EXPIRED.value, PaymentStatus.CANCELLED.value, PaymentStatus.FAILED.value}:
            link.status = target.value
            if target in {PaymentStatus.EXPIRED, PaymentStatus.FAILED}:
                self._record_nonrecovery(link, event)
        link.updated_at = self._now()
        self.session.commit()
        return self.get_payment(link.id)

    def _record_recovery(self, link: PaymentLink, event: PaymentWebhookEvent) -> None:
        intervention = self.interventions.get_intervention(link.intervention_id)
        if intervention.status == InterventionStatus.AWAITING_OUTCOME.value:
            self.interventions.record_outcome(link.intervention_id, InterventionOutcomeCreate(status="RECOVERED", recovered_amount_paise=event.amount_paise, currency=event.currency, outcome_reference=event.provider_payment_id or event.provider_event_id, occurred_at=event.occurred_at, source="payment_provider"))

    def _record_nonrecovery(self, link: PaymentLink, event: PaymentWebhookEvent) -> None:
        intervention = self.interventions.get_intervention(link.intervention_id)
        if intervention.status == InterventionStatus.AWAITING_OUTCOME.value:
            status = "EXPIRED" if event.status == PaymentStatus.EXPIRED else "FAILED"
            self.interventions.record_outcome(link.intervention_id, InterventionOutcomeCreate(status=status, recovered_amount_paise=0, currency=event.currency, outcome_reference=event.provider_event_id, occurred_at=event.occurred_at, source="payment_provider"))
