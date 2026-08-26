from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import RetryAttempt, ScheduledRetry
from backend.app.interventions.service import InterventionService

from .context import RetryContext
from .provider import LocalDeterministicRetryProvider, RetryProvider
from .scheduler import deterministic_retry_time
from .versions import RETRY_VERSION


class RetryService:
    def __init__(self, session: Session, provider: RetryProvider | None = None) -> None:
        self.session, self.provider = session, provider or LocalDeterministicRetryProvider()
        self.interventions = InterventionService(session)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def schedule(self, intervention_id: str) -> ScheduledRetry:
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "RETRY_LATER" or intervention.decision.selected_action != "RETRY_LATER":
            raise ValueError("scheduling is only allowed for stored RETRY_LATER intervention")
        existing = self.session.scalar(select(ScheduledRetry).where(ScheduledRetry.intervention_id == intervention_id))
        if existing is not None:
            return existing
        key = hashlib.sha256(f"chimera-retry-schedule-v1|{intervention.id}|{intervention.decision_id}".encode()).hexdigest()
        row = ScheduledRetry(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, idempotency_key=key, attempt_number=1, scheduled_at=deterministic_retry_time(intervention.recovery_case.decision_timestamp), schedule_reason="deterministic_one_day_after_decision", eligibility_status="PENDING", execution_status="SCHEDULED")
        self.session.add(row)
        self.session.commit()
        return self.get_schedule(row.id)

    def list_scheduled(self, due_only: bool = False) -> list[ScheduledRetry]:
        query = select(ScheduledRetry).order_by(ScheduledRetry.scheduled_at.asc(), ScheduledRetry.id.asc())
        rows = list(self.session.scalars(query))
        if due_only:
            now = self._now()
            rows = [row for row in rows if row.scheduled_at <= now and row.execution_status == "SCHEDULED"]
        return rows

    def get_schedule(self, retry_id: str) -> ScheduledRetry:
        row = self.session.get(ScheduledRetry, retry_id)
        if row is None:
            raise ValueError("scheduled retry not found")
        return row

    def execute_now(self, intervention_id: str) -> RetryAttempt:
        intervention = self.interventions.get_intervention(intervention_id)
        if intervention.action != "RETRY_NOW" or intervention.decision.selected_action != "RETRY_NOW":
            raise ValueError("immediate retry requires stored RETRY_NOW intervention")
        return self._execute(intervention)

    def execute_scheduled(self, retry_id: str) -> RetryAttempt:
        schedule = self.get_schedule(retry_id)
        if schedule.execution_status == "EXECUTED":
            return self._latest_attempt(schedule.intervention_id)
        now = self._now()
        scheduled_at = schedule.scheduled_at if schedule.scheduled_at.tzinfo else schedule.scheduled_at.replace(tzinfo=timezone.utc)
        if scheduled_at > now:
            raise ValueError("retry is not yet eligible")
        intervention = self.interventions.get_intervention(schedule.intervention_id)
        result = self._execute(intervention)
        schedule.eligibility_status, schedule.execution_status, schedule.executed_at = "ELIGIBLE", "EXECUTED", result.completed_at
        self.session.commit()
        return result

    def attempts(self, intervention_id: str) -> list[RetryAttempt]:
        self.interventions.get_intervention(intervention_id)
        return list(self.session.scalars(select(RetryAttempt).where(RetryAttempt.intervention_id == intervention_id).order_by(RetryAttempt.attempt_number.asc(), RetryAttempt.id.asc())))

    def _execute(self, intervention) -> RetryAttempt:
        existing = self._latest_attempt(intervention.id)
        if existing is not None:
            return existing
        if intervention.status == "READY":
            self.interventions.execute(intervention.id)
            intervention = self.interventions.get_intervention(intervention.id)
        if intervention.status != "AWAITING_OUTCOME":
            raise ValueError(f"retry requires executable intervention, got {intervention.status}")
        key = hashlib.sha256(f"chimera-retry-v1|{intervention.id}|1|{self.provider.name}".encode()).hexdigest()
        context = RetryContext(intervention_id=intervention.id, recovery_case_id=intervention.recovery_case_id, decision_id=intervention.decision_id, action=intervention.action, amount_paise=intervention.recovery_case.amount_paise, currency=intervention.recovery_case.currency, attempt_number=1, idempotency_key=key)
        started = self._now()
        try:
            provider_result = self.provider.retry(context)
        except Exception as exc:
            provider_result = type("RetryFailure", (), {"provider_reference": "", "status": "FAILED", "validated_result": {"error_code": "provider_request_failed", "payment_recovery_confirmed": False}, "completed_at": self._now()})()
        result_json = dict(provider_result.validated_result)
        row = RetryAttempt(recovery_case_id=intervention.recovery_case_id, intervention_id=intervention.id, decision_id=intervention.decision_id, action=intervention.action, idempotency_key=key, attempt_number=1, provider=self.provider.name, provider_reference=provider_result.provider_reference, status=provider_result.status, request_hash=hashlib.sha256(json.dumps(context.model_dump(), sort_keys=True).encode()).hexdigest(), result_hash=hashlib.sha256(json.dumps(result_json, sort_keys=True).encode()).hexdigest(), validated_result_json=result_json, started_at=started, completed_at=provider_result.completed_at)
        self.session.add(row)
        self.session.commit()
        return row

    def _latest_attempt(self, intervention_id: str) -> RetryAttempt | None:
        return self.session.scalar(select(RetryAttempt).where(RetryAttempt.intervention_id == intervention_id).order_by(RetryAttempt.attempt_number.desc(), RetryAttempt.id.desc()))
