from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.db.models import Decision, Intervention, InterventionEvent, InterventionExecution, InterventionOutcome
from backend.chimera_simulator.models import ACTIONS

from .context import ApprovedExecutionContext, build_approved_context, context_hash
from .errors import (
    ActionMismatchError,
    DecisionNotFoundError,
    ExecutorUnavailableError,
    InterventionNotFoundError,
    InvalidOutcomeError,
)
from .executors import InterventionExecutor, default_executors
from .idempotency import execution_idempotency_key, intervention_idempotency_key
from .outcomes import OutcomeStatus
from .state_machine import InterventionStatus, TERMINAL_STATUSES, validate_transition


class InterventionService:
    """Operational lifecycle service; it never invokes the deterministic decision engine."""

    def __init__(self, session: Session, executors: dict[str, InterventionExecutor] | None = None) -> None:
        self.session = session
        self.executors = executors or default_executors()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _get_decision(self, decision_id: str) -> Decision:
        result = self.session.execute(
            select(Decision)
            .options(joinedload(Decision.recovery_case), selectinload(Decision.candidates))
            .where(Decision.id == decision_id)
        )
        decision = result.unique().scalar_one_or_none()
        if decision is None:
            raise DecisionNotFoundError("decision not found")
        return decision

    def get_intervention(self, intervention_id: str) -> Intervention:
        result = self.session.execute(
            select(Intervention)
            .options(
                joinedload(Intervention.recovery_case),
                joinedload(Intervention.decision),
                selectinload(Intervention.executions),
                selectinload(Intervention.events),
                selectinload(Intervention.outcomes),
            )
            .where(Intervention.id == intervention_id)
        )
        intervention = result.unique().scalar_one_or_none()
        if intervention is None:
            raise InterventionNotFoundError("intervention not found")
        return intervention

    def create_from_decision(self, decision_id: str) -> tuple[Intervention, bool]:
        decision = self._get_decision(decision_id)
        action = decision.selected_action
        if action not in ACTIONS:
            raise ActionMismatchError("stored decision contains an unknown action")
        key = intervention_idempotency_key(decision_id=decision.id, decision_run_id=decision.decision_run_id, action=action)
        existing = self.session.scalar(select(Intervention).where(Intervention.idempotency_key == key))
        if existing is not None:
            if existing.action != action or existing.decision_id != decision.id:
                raise ActionMismatchError("idempotency key resolves to a different stored action")
            return self.get_intervention(existing.id), False

        intervention = Intervention(
            recovery_case_id=decision.recovery_case_id,
            decision_id=decision.id,
            action=action,
            status=InterventionStatus.CREATED.value,
            priority=0,
            idempotency_key=key,
            lifecycle_version=0,
        )
        self.session.add(intervention)
        try:
            self.session.flush()
            self._event(intervention, "INTERVENTION_CREATED", {"action": action})
            if action == "DO_NOTHING":
                self._change_status(intervention, InterventionStatus.COMPLETED)
                intervention.completed_at = self._now()
                self._event(intervention, "INTERVENTION_COMPLETED", {"reason": "No intervention selected by deterministic policy"})
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.session.scalar(select(Intervention).where(Intervention.idempotency_key == key))
            if existing is not None:
                return self.get_intervention(existing.id), False
            raise ActionMismatchError("intervention could not be created") from exc
        return self.get_intervention(intervention.id), True

    def list_interventions(self, *, status: str | None = None, action: str | None = None, recovery_case_id: str | None = None, queue_only: bool = False) -> list[Intervention]:
        query = select(Intervention).options(joinedload(Intervention.decision), joinedload(Intervention.recovery_case))
        filters = []
        if status:
            filters.append(Intervention.status == status)
        if action:
            filters.append(Intervention.action == action)
        if recovery_case_id:
            filters.append(Intervention.recovery_case_id == recovery_case_id)
        if queue_only:
            filters.append(Intervention.status.in_([InterventionStatus.QUEUED.value, InterventionStatus.READY.value]))
        query = query.where(*filters).order_by(Intervention.priority.desc(), Intervention.created_at.asc(), Intervention.id.asc())
        return list(self.session.scalars(query))

    def queue(self, intervention_id: str) -> Intervention:
        intervention = self.get_intervention(intervention_id)
        if intervention.status == InterventionStatus.COMPLETED.value:
            return intervention
        if intervention.status == InterventionStatus.CREATED.value:
            self._change_status(intervention, InterventionStatus.QUEUED)
            intervention.queued_at = self._now()
            self._event(intervention, "INTERVENTION_QUEUED", {})
        if intervention.status == InterventionStatus.QUEUED.value:
            self._change_status(intervention, InterventionStatus.READY)
            self._event(intervention, "INTERVENTION_READY", {})
        self.session.commit()
        return self.get_intervention(intervention.id)

    def execute(self, intervention_id: str) -> InterventionExecution:
        intervention = self.get_intervention(intervention_id)
        if intervention.status == InterventionStatus.COMPLETED.value:
            raise ExecutorUnavailableError("DO_NOTHING has no external execution")
        if intervention.status == InterventionStatus.AWAITING_OUTCOME.value:
            latest = self._latest_execution(intervention.id)
            if latest is not None:
                return latest
        if intervention.status != InterventionStatus.READY.value:
            if intervention.status in TERMINAL_STATUSES:
                raise ExecutorUnavailableError(f"intervention is terminal: {intervention.status}")
            raise ExecutorUnavailableError(f"intervention status {intervention.status} is not ready for execution")

        context = build_approved_context(intervention)
        executor = self.executors.get(intervention.action)
        if executor is None:
            raise ExecutorUnavailableError(f"no executor configured for action {intervention.action}")
        attempt_number = 1 + int(self.session.scalar(select(func.max(InterventionExecution.attempt_number)).where(InterventionExecution.intervention_id == intervention.id)) or 0)
        key = execution_idempotency_key(intervention_id=intervention.id, attempt_number=attempt_number, action=intervention.action)
        existing = self.session.scalar(select(InterventionExecution).where(InterventionExecution.idempotency_key == key))
        if existing is not None:
            return existing

        started_at = self._now()
        self._change_status(intervention, InterventionStatus.EXECUTING)
        intervention.started_at = started_at
        self._event(intervention, "EXECUTION_STARTED", {"attempt_number": attempt_number, "executor_type": executor.executor_type})
        result = executor.execute(context)
        completed_at = self._now()
        response_json = dict(result.response)
        result_hash = self._hash(response_json)
        execution = InterventionExecution(
            intervention_id=intervention.id,
            attempt_number=attempt_number,
            executor_type=result.executor_type,
            status=result.status,
            idempotency_key=key,
            provider_reference=result.provider_reference,
            request_hash=context_hash(context),
            result_hash=result_hash,
            error_code=result.error_code,
            error_message_safe=result.error_message_safe,
            started_at=started_at,
            completed_at=completed_at,
            response_json=response_json,
        )
        self.session.add(execution)
        if result.status == "ACCEPTED":
            self._event(intervention, "EXECUTION_ACCEPTED", {"attempt_number": attempt_number, "provider_reference": result.provider_reference})
            self._change_status(intervention, InterventionStatus.AWAITING_OUTCOME)
            self._event(intervention, "AWAITING_OUTCOME", {})
        else:
            self._change_status(intervention, InterventionStatus.FAILED)
            intervention.completed_at = completed_at
            self._event(intervention, "EXECUTION_FAILED", {"attempt_number": attempt_number, "error_code": result.error_code})
        self.session.commit()
        self.session.refresh(execution)
        return execution

    def record_outcome(self, intervention_id: str, payload) -> InterventionOutcome:
        intervention = self.get_intervention(intervention_id)
        if intervention.status in TERMINAL_STATUSES:
            raise InvalidOutcomeError(f"terminal intervention outcome cannot be overwritten: {intervention.status}")
        if intervention.status != InterventionStatus.AWAITING_OUTCOME.value:
            raise InvalidOutcomeError(f"outcome requires AWAITING_OUTCOME, got {intervention.status}")
        if payload.recovered_amount_paise is not None and payload.recovered_amount_paise < 0:
            raise InvalidOutcomeError("recovered amount cannot be negative")
        case = intervention.recovery_case
        if payload.recovered_amount_paise is not None and payload.recovered_amount_paise > case.amount_paise:
            raise InvalidOutcomeError("recovered amount cannot exceed case amount")
        if payload.status == OutcomeStatus.RECOVERED.value and payload.currency != case.currency:
            raise InvalidOutcomeError("recovered outcome currency must match the case currency")

        outcome = InterventionOutcome(
            intervention_id=intervention.id,
            status=payload.status,
            recovered_amount_paise=payload.recovered_amount_paise,
            currency=payload.currency,
            outcome_reference=payload.outcome_reference,
            occurred_at=payload.occurred_at,
            source=payload.source,
        )
        self.session.add(outcome)
        self._event(intervention, "OUTCOME_RECORDED", {"status": payload.status, "source": payload.source})
        terminal_target = {
            OutcomeStatus.RECOVERED.value: InterventionStatus.RECOVERED,
            OutcomeStatus.NOT_RECOVERED.value: InterventionStatus.FAILED,
            OutcomeStatus.FAILED.value: InterventionStatus.FAILED,
            OutcomeStatus.EXPIRED.value: InterventionStatus.EXPIRED,
        }.get(payload.status)
        if terminal_target is not None:
            self._change_status(intervention, terminal_target)
            intervention.completed_at = self._now()
            event_type = "RECOVERY_CONFIRMED" if terminal_target == InterventionStatus.RECOVERED else "RECOVERY_FAILED"
            self._event(intervention, event_type, {"status": payload.status})
        self.session.commit()
        self.session.refresh(outcome)
        return outcome

    def executions(self, intervention_id: str) -> list[InterventionExecution]:
        self.get_intervention(intervention_id)
        return list(self.session.scalars(select(InterventionExecution).where(InterventionExecution.intervention_id == intervention_id).order_by(InterventionExecution.attempt_number.asc(), InterventionExecution.id.asc())))

    def events(self, intervention_id: str) -> list[InterventionEvent]:
        self.get_intervention(intervention_id)
        return list(self.session.scalars(select(InterventionEvent).where(InterventionEvent.intervention_id == intervention_id).order_by(InterventionEvent.sequence_number.asc(), InterventionEvent.id.asc())))

    def _latest_execution(self, intervention_id: str) -> InterventionExecution | None:
        return self.session.scalar(select(InterventionExecution).where(InterventionExecution.intervention_id == intervention_id).order_by(InterventionExecution.attempt_number.desc(), InterventionExecution.id.desc()))

    def _change_status(self, intervention: Intervention, target: InterventionStatus) -> None:
        validate_transition(intervention.status, target)
        intervention.status = target.value
        intervention.lifecycle_version += 1

    def _event(self, intervention: Intervention, event_type: str, payload: dict) -> None:
        persisted_sequence = int(self.session.scalar(select(func.max(InterventionEvent.sequence_number)).where(InterventionEvent.intervention_id == intervention.id)) or 0)
        pending_sequence = max(
            (event.sequence_number for event in self.session.new if isinstance(event, InterventionEvent) and event.intervention_id == intervention.id),
            default=0,
        )
        next_sequence = max(persisted_sequence, pending_sequence) + 1
        self.session.add(
            InterventionEvent(
                intervention_id=intervention.id,
                recovery_case_id=intervention.recovery_case_id,
                decision_id=intervention.decision_id,
                event_type=event_type,
                actor="system",
                payload_json=payload,
                sequence_number=next_sequence,
            )
        )

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
