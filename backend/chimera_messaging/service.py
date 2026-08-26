from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import MessageAttempt, MessagingEvent, PaymentLink
from backend.app.interventions.service import InterventionService

from .context import MessagingContext
from .events import payload_hash
from .providers import MessagingProvider
from .templates import render_message
from .validation import validate_messaging_context
from .versions import MESSAGING_VERSION


class MessagingService:
    def __init__(self, session: Session, provider: MessagingProvider, payment_service=None) -> None:
        self.session, self.provider, self.payment_service = session, provider, payment_service
        self.interventions = InterventionService(session)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def list_messages(self, intervention_id: str) -> list[MessageAttempt]:
        self.interventions.get_intervention(intervention_id)
        return list(self.session.scalars(select(MessageAttempt).options(selectinload(MessageAttempt.events)).where(MessageAttempt.intervention_id == intervention_id).order_by(MessageAttempt.attempt_number.asc(), MessageAttempt.id.asc())))

    def send(self, intervention_id: str) -> MessageAttempt:
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "SEND_MESSAGE" or intervention.decision.selected_action != "SEND_MESSAGE":
            raise ValueError("messaging is only allowed for stored SEND_MESSAGE intervention")
        active_link = self._active_payment_link(intervention_id)
        if active_link is None and self.payment_service is not None:
            active_link = self.payment_service.create_for_message(intervention_id)
        context = validate_messaging_context(MessagingContext(intervention_id=intervention.id, recovery_case_id=intervention.recovery_case_id, decision_id=intervention.decision_id, selected_action=intervention.action, customer_id=intervention.recovery_case.customer_id, language="en", amount_paise=intervention.recovery_case.amount_paise, currency=intervention.recovery_case.currency, payment_method=intervention.recovery_case.payment_method, failure_reason=intervention.recovery_case.failure_reason, incident_flag=intervention.recovery_case.incident_flag, payment_link=active_link.short_url if active_link else None))
        if intervention.status == "READY":
            self.interventions.execute(intervention.id)
            intervention = self.interventions.get_intervention(intervention.id)
        existing = self.session.scalar(select(MessageAttempt).where(MessageAttempt.intervention_id == intervention.id).order_by(MessageAttempt.attempt_number.asc(), MessageAttempt.id.asc()))
        if existing is not None:
            return self.get_message(existing.id)
        key = __import__("hashlib").sha256(f"chimera-message-v1|{intervention.id}|{self.provider.name}".encode()).hexdigest()
        template, version, content, content_hash = render_message(context)
        try:
            result = self.provider.send_message(context, content, key)
        except Exception as exc:
            row = MessageAttempt(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, provider=self.provider.name, provider_mode=self.provider.mode, idempotency_key=key, attempt_number=1, template_key=template, template_version=version, rendered_content_hash=content_hash, provider_message_id=None, status="FAILED", delivery_state="FAILED", sent_at=self._now())
            self.session.add(row)
            self.session.flush()
            self.session.add(MessagingEvent(message_attempt_id=row.id, provider=self.provider.name, provider_mode=self.provider.mode, provider_event_id=f"failed-{row.id}", event_type="message.failed", delivery_state="FAILED", signature_verified=False, occurred_at=row.sent_at, payload_hash=payload_hash({"delivery_state": "FAILED"}), payload_json={"delivery_state": "FAILED", "failure_classification": "provider_request_failed", "processing_result": "failed"}))
            self.session.commit()
            raise ValueError("provider_request_failed") from exc
        row = MessageAttempt(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, provider=self.provider.name, provider_mode=self.provider.mode, idempotency_key=key, attempt_number=1, template_key=template, template_version=version, rendered_content_hash=content_hash, provider_message_id=result.provider_message_id, status=result.status, delivery_state=result.delivery_state, sent_at=result.sent_at)
        self.session.add(row)
        self.session.flush()
        self.session.add(MessagingEvent(message_attempt_id=row.id, provider=self.provider.name, provider_mode=self.provider.mode, provider_event_id=f"sent-{row.id}", event_type="message.sent", delivery_state=result.delivery_state, signature_verified=False, occurred_at=result.sent_at, payload_hash=payload_hash({"provider_message_id": result.provider_message_id, "delivery_state": result.delivery_state}), payload_json={"provider_message_id": result.provider_message_id, "delivery_state": result.delivery_state}))
        self.session.commit()
        return self.get_message(row.id)

    def get_message(self, message_id: str) -> MessageAttempt:
        row = self.session.scalar(select(MessageAttempt).options(selectinload(MessageAttempt.events)).where(MessageAttempt.id == message_id))
        if row is None:
            raise ValueError("message not found")
        return row

    def handle_webhook(self, provider_name: str, raw_body: bytes, signature: str, provider_event_id: str | None = None, webhook_url: str | None = None) -> MessageAttempt:
        if provider_name != self.provider.name or not self.provider.verify_webhook(raw_body, signature, webhook_url):
            raise ValueError("invalid_webhook_signature")
        try:
            parsed = self.provider.parse_webhook(raw_body, provider_event_id)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            raise ValueError("invalid_webhook_payload") from exc
        if not parsed.get("provider_message_id") or not parsed.get("provider_event_id"):
            raise ValueError("invalid_webhook_payload")
        attempt = self.session.scalar(select(MessageAttempt).where(MessageAttempt.provider == provider_name, MessageAttempt.provider_message_id == parsed["provider_message_id"]))
        if attempt is None:
            raise ValueError("message not found for provider reference")
        existing = self.session.scalar(select(MessagingEvent).where(MessagingEvent.provider == provider_name, MessagingEvent.provider_event_id == parsed["provider_event_id"]))
        if existing is not None:
            return self.get_message(attempt.id)
        occurred = parsed.get("occurred_at")
        current = str(attempt.delivery_state).upper()
        incoming = str(parsed["delivery_state"]).upper()
        terminal = {"DELIVERED", "FAILED", "UNDELIVERABLE", "CANCELED", "CANCELLED"}
        processing_result = "ignored_terminal_state" if current in terminal and incoming != current else "applied"
        self.session.add(MessagingEvent(message_attempt_id=attempt.id, provider=provider_name, provider_mode=self.provider.mode, provider_event_id=parsed["provider_event_id"], event_type=parsed["event_type"], delivery_state=parsed["delivery_state"], signature_verified=True, occurred_at=occurred, payload_hash=payload_hash(parsed), payload_json={"provider_message_id": parsed["provider_message_id"], "delivery_state": parsed["delivery_state"], "processing_result": processing_result}))
        if processing_result == "applied":
            attempt.delivery_state = parsed["delivery_state"]
        self.session.commit()
        return self.get_message(attempt.id)

    def _active_payment_link(self, intervention_id: str):
        now = self._now()
        links = list(self.session.scalars(select(PaymentLink).where(PaymentLink.intervention_id == intervention_id, PaymentLink.status == "ACTIVE").order_by(PaymentLink.created_at.desc(), PaymentLink.id.desc())))
        return next((link for link in links if link.expires_at is None or link.expires_at > now), None)
