from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import AuditLog, Escalation, EscalationEvent
from backend.app.interventions.service import InterventionService
from backend.app.interventions.state_machine import InterventionStatus
from backend.chimera_payments.service import PaymentService
from backend.chimera_retry.service import RetryService
from backend.chimera_voice.schemas import VoiceScenario
from backend.chimera_voice.service import VoiceService
from backend.chimera_messaging.service import MessagingService

from .schemas import EscalationStatus


class EscalationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.interventions = InterventionService(session)

    def create(self, intervention_id: str, reason: str) -> Escalation:
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "ESCALATE" or intervention.decision.selected_action != "ESCALATE":
            raise ValueError("escalation requires stored ESCALATE intervention")
        existing = self.session.scalar(select(Escalation).where(Escalation.intervention_id == intervention_id))
        if existing is not None:
            return self.get(existing.id)
        if intervention.status == InterventionStatus.READY.value:
            self.interventions.execute(intervention.id)
            intervention = self.interventions.get_intervention(intervention.id)
        if intervention.status != InterventionStatus.AWAITING_OUTCOME.value:
            raise ValueError(f"escalation requires executable intervention, got {intervention.status}")
        key = hashlib.sha256(f"chimera-escalation-v1|{intervention.id}|{intervention.decision_id}".encode()).hexdigest()
        row = Escalation(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, escalation_reason=reason, context_json={"customer_id": intervention.recovery_case.customer_id, "amount_paise": intervention.recovery_case.amount_paise, "currency": intervention.recovery_case.currency, "failure_reason": intervention.recovery_case.failure_reason, "payment_method": intervention.recovery_case.payment_method, "incident_flag": intervention.recovery_case.incident_flag, "decision_id": intervention.decision_id, "selected_action": intervention.action}, priority=intervention.priority, idempotency_key=key, status=EscalationStatus.OPEN.value)
        self.session.add(row)
        self.session.flush()
        self._event(row, "ESCALATION_OPENED", {"reason": reason})
        self.session.add(AuditLog(recovery_case_id=row.recovery_case_id, decision_id=row.decision_id, event_type="ESCALATION_OPENED", actor="escalation_service", payload_json={"escalation_id": row.id, "status": row.status}))
        self.session.commit()
        return self.get(row.id)

    def get(self, escalation_id: str) -> Escalation:
        row = self.session.scalar(select(Escalation).options(selectinload(Escalation.events)).where(Escalation.id == escalation_id))
        if row is None:
            raise ValueError("escalation not found")
        row.events.sort(key=lambda value: (value.sequence_number, value.id))
        return row

    def list(self) -> list[Escalation]:
        return list(self.session.scalars(select(Escalation).options(selectinload(Escalation.events)).order_by(Escalation.created_at.asc(), Escalation.id.asc())))

    def transition(self, escalation_id: str, target: EscalationStatus) -> Escalation:
        row = self.get(escalation_id)
        allowed = {EscalationStatus.OPEN: {EscalationStatus.ACKNOWLEDGED, EscalationStatus.CANCELLED}, EscalationStatus.ACKNOWLEDGED: {EscalationStatus.IN_PROGRESS, EscalationStatus.RESOLVED, EscalationStatus.CANCELLED}, EscalationStatus.IN_PROGRESS: {EscalationStatus.RESOLVED, EscalationStatus.CANCELLED}, EscalationStatus.RESOLVED: set(), EscalationStatus.CANCELLED: set()}
        if target not in allowed[EscalationStatus(row.status)]:
            if row.status == target.value:
                return row
            raise ValueError(f"invalid escalation transition: {row.status} -> {target.value}")
        row.status = target.value
        row.updated_at = datetime.now(timezone.utc)
        self._event(row, f"ESCALATION_{target.value}", {})
        self.session.commit()
        return self.get(row.id)

    def _event(self, row: Escalation, event_type: str, payload: dict) -> None:
        sequence = int(self.session.scalar(select(func.max(EscalationEvent.sequence_number)).where(EscalationEvent.escalation_id == row.id)) or 0) + 1
        event = EscalationEvent(escalation_id=row.id, event_type=event_type, status=row.status, actor="operator" if event_type != "ESCALATION_OPENED" else "system", payload_json=payload, sequence_number=sequence)
        self.session.add(event)
        row.events.append(event)


class RecoveryOrchestrator:
    """Routes a persisted intervention; it has no decision-selection authority."""

    def __init__(self, session: Session, messaging: MessagingService, retry: RetryService, payments: PaymentService, voice: VoiceService) -> None:
        self.session = session
        self.interventions = InterventionService(session)
        self.messaging, self.retry, self.payments, self.voice = messaging, retry, payments, voice
        self.escalations = EscalationService(session)

    def route(self, intervention_id: str):
        intervention = self.interventions.get_intervention(intervention_id)
        action = intervention.action
        if action == "SEND_MESSAGE":
            return self.messaging.send(intervention_id)
        if action == "RETRY_NOW":
            return self.retry.execute_now(intervention_id)
        if action == "RETRY_LATER":
            return self.retry.schedule(intervention_id)
        if action == "PAYMENT_LINK":
            return self.payments.create_payment_link(intervention_id)
        if action == "VOICE_RECOVERY":
            return self.voice.start(intervention_id, VoiceScenario.CUSTOMER_AGREES_TO_PAY)[0]
        if action == "ESCALATE":
            return self.escalations.create(intervention_id, "Automated recovery could not safely or effectively proceed")
        if action == "DO_NOTHING":
            existing = self.session.scalar(select(AuditLog).where(AuditLog.recovery_case_id == intervention.recovery_case_id, AuditLog.event_type == "ORCHESTRATOR_DO_NOTHING"))
            if existing is None:
                self.session.add(AuditLog(recovery_case_id=intervention.recovery_case_id, decision_id=intervention.decision_id, event_type="ORCHESTRATOR_DO_NOTHING", actor="orchestrator", payload_json={"reason": "Stored decision selected DO_NOTHING"}))
                self.session.commit()
            return intervention
        raise ValueError("unknown stored intervention action")
