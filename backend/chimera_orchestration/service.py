from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import AuditLog, Escalation, EscalationEvent, PaymentLink, RecoveryCase
from backend.app.domain import CaseStatus, transition
from backend.app.services.case_service import CaseService
from backend.app.interventions.service import InterventionService
from backend.app.interventions.state_machine import InterventionStatus
from backend.chimera_payments.schemas import PaymentStatus
from backend.chimera_payments.service import PaymentService
from backend.chimera_retry.service import RetryService
from backend.chimera_voice.schemas import VoiceScenario
from backend.chimera_voice.service import VoiceService
from backend.chimera_messaging.service import MessagingService

from .schemas import EscalationStatus


class EscalationService:
    def __init__(self, session: Session, provider=None) -> None:
        self.session = session
        self.interventions = InterventionService(session)
        self.provider = provider

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
        provider_mode = getattr(self.provider, "mode", "LOCAL")
        row = Escalation(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, escalation_reason=reason, context_json={"customer_id": intervention.recovery_case.customer_id, "amount_paise": intervention.recovery_case.amount_paise, "currency": intervention.recovery_case.currency, "failure_reason": intervention.recovery_case.failure_reason, "payment_method": intervention.recovery_case.payment_method, "incident_flag": intervention.recovery_case.incident_flag, "decision_id": intervention.decision_id, "selected_action": intervention.action, "notification": {"provider": getattr(self.provider, "name", "internal")}}, priority=intervention.priority, idempotency_key=key, status=EscalationStatus.OPEN.value, provider_mode=provider_mode)
        self.session.add(row)
        self.session.flush()
        self._event(row, "ESCALATION_OPENED", {"reason": reason})
        self.session.add(AuditLog(recovery_case_id=row.recovery_case_id, decision_id=row.decision_id, event_type="ESCALATION_OPENED", actor="escalation_service", payload_json={"escalation_id": row.id, "status": row.status}))
        self.session.commit()
        if self.provider is not None:
            try:
                notification = self.provider.notify(row, reason)
                row.context_json = {**row.context_json, "notification": {"provider": notification.provider, "provider_reference": notification.provider_reference, "status": notification.status}}
                self._event(row, "ESCALATION_NOTIFICATION_SENT", {"provider": notification.provider, "provider_reference": notification.provider_reference, "status": notification.status})
                self.session.commit()
            except Exception as exc:
                self._event(row, "ESCALATION_NOTIFICATION_FAILED", {"provider": getattr(self.provider, "name", "unknown"), "error": str(exc)[:128]})
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

    def __init__(self, session: Session, messaging: MessagingService, retry: RetryService, payments: PaymentService, voice: VoiceService, case_service: CaseService | None = None, escalation_provider=None) -> None:
        self.session = session
        self.interventions = InterventionService(session)
        self.messaging, self.retry, self.payments, self.voice = messaging, retry, payments, voice
        self.escalations = EscalationService(session, escalation_provider)
        self.case_service = case_service

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
            payment = self.payments.create_payment_link(intervention_id)
            try:
                self.messaging.send_for_payment_link(intervention_id, payment.short_url)
            except ValueError:
                # The payment artifact remains usable and the failed delivery
                # is persisted by MessagingService for operator visibility.
                pass
            return payment
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

    def continue_after_payment_outcome(self, payment: PaymentLink):
        """Start one persisted fallback after a payment-link failure.

        The payment provider remains the outcome authority. This method only
        continues a failed recovery after that provider outcome is persisted.
        A single fallback is allowed so a bad provider state cannot create an
        unbounded chain of payment links.
        """
        if payment.status not in {PaymentStatus.FAILED.value, PaymentStatus.EXPIRED.value}:
            return None
        intervention = self.interventions.get_intervention(payment.intervention_id)
        if intervention.action != "PAYMENT_LINK" or intervention.status not in {InterventionStatus.FAILED.value, InterventionStatus.EXPIRED.value}:
            return None
        if self.case_service is None:
            return None

        case = self.session.get(RecoveryCase, payment.recovery_case_id)
        if case is None or case.status not in {
            CaseStatus.DECIDED.value,
            CaseStatus.ACTION_EXECUTED.value,
            CaseStatus.UNRECOVERED.value,
        }:
            return None

        # Repair cases created before the parent-case lifecycle was updated by
        # payment outcomes. This keeps the continuation bounded and makes the
        # recovery path safe to replay for existing failed links.
        if case.status == CaseStatus.DECIDED.value:
            transition(case.status, CaseStatus.ACTION_PENDING)
            case.status = CaseStatus.ACTION_PENDING.value
            transition(case.status, CaseStatus.ACTION_EXECUTED)
            case.status = CaseStatus.ACTION_EXECUTED.value
            transition(case.status, CaseStatus.UNRECOVERED)
            case.status = CaseStatus.UNRECOVERED.value
        elif case.status == CaseStatus.ACTION_EXECUTED.value:
            transition(case.status, CaseStatus.UNRECOVERED)
            case.status = CaseStatus.UNRECOVERED.value
        case.updated_at = datetime.now(timezone.utc)
        follow_up_count = int(
            self.session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.recovery_case_id == case.id,
                    AuditLog.event_type == "AUTOMATIC_FOLLOW_UP_DECISION_CREATED",
                )
            )
            or 0
        )
        if follow_up_count >= 1:
            return None

        decision = self.case_service.create_follow_up_decision(case.id, intervention.decision_id, intervention.action)
        if decision is None:
            return None

        transition(case.status, CaseStatus.ACTION_PENDING)
        case.status = CaseStatus.ACTION_PENDING.value
        case.updated_at = datetime.now(timezone.utc)
        self.session.add(
            AuditLog(
                recovery_case_id=case.id,
                decision_id=decision.id,
                event_type="AUTOMATIC_RECOVERY_REOPENED",
                actor="recovery_orchestrator",
                payload_json={"failed_payment_id": payment.id, "selected_action": decision.selected_action},
            )
        )
        self.session.commit()

        follow_up, _ = self.interventions.create_from_decision(decision.id)
        self.interventions.queue(follow_up.id)
        try:
            result = self.route(follow_up.id)
            if follow_up.action != "RETRY_LATER":
                refreshed = self.interventions.get_intervention(follow_up.id)
                if refreshed.status == InterventionStatus.AWAITING_OUTCOME.value:
                    case = self.session.get(RecoveryCase, case.id)
                    if case is not None and case.status == CaseStatus.ACTION_PENDING.value:
                        transition(case.status, CaseStatus.ACTION_EXECUTED)
                        case.status = CaseStatus.ACTION_EXECUTED.value
                        case.updated_at = datetime.now(timezone.utc)
                        self.session.add(
                            AuditLog(
                                recovery_case_id=case.id,
                                decision_id=decision.id,
                                event_type="AUTOMATIC_FOLLOW_UP_EXECUTED",
                                actor="recovery_orchestrator",
                                payload_json={"selected_action": decision.selected_action, "intervention_id": follow_up.id},
                            )
                        )
                        self.session.commit()
            return result
        except Exception as exc:
            case = self.session.get(RecoveryCase, case.id)
            if case is not None and case.status == CaseStatus.ACTION_PENDING.value:
                transition(case.status, CaseStatus.UNRECOVERED)
                case.status = CaseStatus.UNRECOVERED.value
                case.updated_at = datetime.now(timezone.utc)
                self.session.add(
                    AuditLog(
                        recovery_case_id=case.id,
                        decision_id=decision.id,
                        event_type="AUTOMATIC_RECOVERY_FAILED",
                        actor="recovery_orchestrator",
                        payload_json={"selected_action": decision.selected_action, "error": str(exc)[:255]},
                    )
                )
                self.session.commit()
            return None
