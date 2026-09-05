from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.db.models import (
    ActionExecution, AuditLog, Decision, Escalation, Explanation, Intervention,
    InterventionEvent, PaymentEvent, PaymentLink, PaymentOrder, RecoveryCase, RetryAttempt,
    ScheduledRetry, VoiceCall, VoiceEvent, MessageAttempt,
)
from backend.app.domain import DomainError


def _iso(value):
    return value.isoformat() if value is not None else None


def _record(row, *, event_type: str, source: str, timestamp, payload: dict[str, Any], provider_mode: str | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_type": event_type,
        "source": source,
        "timestamp": _iso(timestamp),
        "provider_mode": provider_mode,
        "payload": payload,
    }


class RecoveryJourneyService:
    """Builds a persisted, chronological projection; it never recomputes decisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, case_id: str) -> dict[str, Any]:
        result = self.session.execute(
            select(RecoveryCase).options(
                selectinload(RecoveryCase.decisions).selectinload(Decision.candidates),
                selectinload(RecoveryCase.decisions).selectinload(Decision.explanations),
                selectinload(RecoveryCase.explanations),
                selectinload(RecoveryCase.executions),
                selectinload(RecoveryCase.audit_logs),
                selectinload(RecoveryCase.intervention_events),
                selectinload(RecoveryCase.interventions).selectinload(Intervention.executions),
                selectinload(RecoveryCase.interventions).selectinload(Intervention.events),
                selectinload(RecoveryCase.interventions).selectinload(Intervention.outcomes),
                selectinload(RecoveryCase.payment_links).selectinload(PaymentLink.events),
                selectinload(RecoveryCase.payment_orders).selectinload(PaymentOrder.events),
                selectinload(RecoveryCase.message_attempts).selectinload(MessageAttempt.events),
                selectinload(RecoveryCase.retry_attempts),
                selectinload(RecoveryCase.scheduled_retries),
                selectinload(RecoveryCase.escalations).selectinload(Escalation.events),
                selectinload(RecoveryCase.interventions).selectinload(Intervention.voice_calls).selectinload(VoiceCall.turns),
                selectinload(RecoveryCase.interventions).selectinload(Intervention.voice_calls).selectinload(VoiceCall.events),
            ).where(RecoveryCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        if case is None:
            raise DomainError("recovery case not found")

        decisions = sorted(
            enumerate(case.decisions),
            key=lambda item: (item[1].created_at, item[1].decision_timestamp, item[0]),
            reverse=True,
        )
        decision = decisions[0][1] if decisions else None
        interventions = sorted(case.interventions, key=lambda row: (row.created_at, row.id))
        latest_explanation = max(case.explanations, key=lambda row: (row.generated_at, row.id), default=None)
        audit = self._audit(case)
        return {
            "case": {
                "id": case.id, "external_event_id": case.external_event_id, "payment_id": case.payment_id,
                "customer_id": case.customer_id, "customer_phone": case.customer_phone, "amount_paise": case.amount_paise, "currency": case.currency,
                "failure_reason": case.failure_reason, "incident_flag": case.incident_flag,
                "payment_method": case.payment_method, "decision_timestamp": _iso(case.decision_timestamp),
                "status": case.status, "created_at": _iso(case.created_at), "updated_at": _iso(case.updated_at),
            },
            "decision": self._decision(decision),
            "latest_explanation": self._explanation(latest_explanation),
            "interventions": [self._intervention(row) for row in interventions],
            "execution": [self._execution(row) for row in sorted(case.executions, key=lambda row: (row.created_at, row.id))],
            "payments": [self._payment(row) for row in sorted(case.payment_links, key=lambda row: (row.created_at, row.id))],
            "initial_orders": [self._initial_order(row) for row in sorted(case.payment_orders, key=lambda row: (row.created_at, row.id))],
            "messages": [self._message(row) for row in sorted(case.message_attempts, key=lambda row: (row.created_at, row.id))],
            "retries": [self._retry(row) for row in sorted(case.retry_attempts, key=lambda row: (row.created_at, row.id))],
            "scheduled_retries": [self._schedule(row) for row in sorted(case.scheduled_retries, key=lambda row: (row.created_at, row.id))],
            "voice_calls": [self._voice(row) for intervention in interventions for row in sorted(intervention.voice_calls, key=lambda row: (row.created_at, row.id))],
            "escalations": [self._escalation(row) for row in sorted(case.escalations, key=lambda row: (row.created_at, row.id))],
            "audit_trail": audit,
        }

    @staticmethod
    def _initial_order(row):
        return {"id": row.id, "provider": row.provider, "provider_mode": row.provider_mode,
                "provider_order_id": row.provider_order_id, "amount_paise": row.amount_paise,
                "currency": row.currency, "status": row.status,
                "provider_payment_id": row.provider_payment_id, "failure_reason": row.failure_reason,
                "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at),
                "events": [_record(item, event_type=item.event_type, source=item.source,
                                    timestamp=item.occurred_at, payload=item.payload_json,
                                    provider_mode=item.provider_mode)
                           for item in sorted(row.events, key=lambda x: (x.occurred_at, x.id))]}

    @staticmethod
    def _decision(row):
        if row is None:
            return None
        return {"id": row.id, "selected_action": row.selected_action, "predicted_probability": row.predicted_probability,
                "expected_gross_recovery_paise": row.expected_gross_recovery_paise, "expected_net_value_paise": row.expected_net_value_paise,
                "model_version": row.model_version, "feature_schema_version": row.feature_schema_version,
                "engine_version": row.engine_version, "simulator_version": row.simulator_version,
                "decision_timestamp": _iso(row.decision_timestamp), "created_at": _iso(row.created_at),
                "trace_json": row.trace_json, "candidates": [{"action": c.action, "status": c.status, "predicted_probability": c.predicted_probability,
                "expected_net_value_paise": c.expected_net_value_paise, "rank": c.rank} for c in sorted(row.candidates, key=lambda c: (c.rank or 999, c.action))]}

    @staticmethod
    def _explanation(row):
        if row is None:
            return None
        return {"id": row.id, "source": row.explanation_source, "provider": row.provider, "model_name": row.model_name,
                "generated_at": _iso(row.generated_at), "fallback_reason": row.fallback_reason,
                "structured_explanation": row.structured_explanation}

    @staticmethod
    def _intervention(row):
        return {"id": row.id, "decision_id": row.decision_id, "action": row.action, "status": row.status,
                "priority": row.priority, "created_at": _iso(row.created_at), "queued_at": _iso(row.queued_at),
                "started_at": _iso(row.started_at), "completed_at": _iso(row.completed_at),
                "executions": [RecoveryJourneyService._execution(item) for item in sorted(row.executions, key=lambda x: (x.created_at, x.id))],
                "outcomes": [{"id": item.id, "status": item.status, "recovered_amount_paise": item.recovered_amount_paise,
                              "occurred_at": _iso(item.occurred_at), "source": item.source} for item in sorted(row.outcomes, key=lambda x: (x.occurred_at, x.id))],
                "events": [_record(item, event_type=item.event_type, source=item.actor, timestamp=item.created_at, payload=item.payload_json) for item in sorted(row.events, key=lambda x: (x.created_at, x.id))]}

    @staticmethod
    def _execution(row):
        return {"id": row.id, "action": getattr(row, "action", None), "provider_mode": getattr(row, "provider_mode", "LOCAL"), "status": row.status, "provider_reference": getattr(row, "provider_reference", None),
                "error_code": getattr(row, "error_code", None), "executed_at": _iso(getattr(row, "executed_at", None)), "created_at": _iso(row.created_at),
                "response_json": getattr(row, "response_json", {})}

    @staticmethod
    def _payment(row):
        return {"id": row.id, "intervention_id": row.intervention_id, "provider": row.provider, "provider_mode": row.provider_mode, "status": row.status,
                "amount_paise": row.amount_paise, "short_url": row.short_url, "created_at": _iso(row.created_at),
                "events": [_record(item, event_type=item.event_type, source=item.source, timestamp=item.occurred_at, payload=item.payload_json, provider_mode=item.provider_mode)
                           for item in sorted(row.events, key=lambda x: (x.occurred_at, x.id))]}

    @staticmethod
    def _message(row):
        failed_event = next((item for item in reversed(sorted(row.events, key=lambda x: (x.occurred_at, x.id))) if item.event_type == "message.failed"), None)
        failure_reason = failed_event.payload_json.get("failure_reason") if failed_event else None
        failure_code = failed_event.payload_json.get("failure_classification") if failed_event else None
        return {"id": row.id, "provider": row.provider, "provider_mode": row.provider_mode, "status": row.status,
                "delivery_state": row.delivery_state, "provider_message_id": row.provider_message_id, "failure_reason": failure_reason, "failure_code": failure_code, "created_at": _iso(row.created_at),
                "events": [_record(item, event_type=item.event_type, source="provider", timestamp=item.occurred_at, payload=item.payload_json, provider_mode=item.provider_mode)
                           for item in sorted(row.events, key=lambda x: (x.occurred_at, x.id))]}

    @staticmethod
    def _retry(row):
        return {"id": row.id, "action": row.action, "provider": row.provider, "provider_mode": row.provider_mode, "status": row.status,
                "provider_reference": row.provider_reference, "validated_result_json": row.validated_result_json, "created_at": _iso(row.created_at)}

    @staticmethod
    def _schedule(row):
        return {"id": row.id, "provider_mode": row.provider_mode, "scheduled_at": _iso(row.scheduled_at),
                "execution_status": row.execution_status, "eligibility_status": row.eligibility_status, "executed_at": _iso(row.executed_at), "created_at": _iso(row.created_at)}

    @staticmethod
    def _voice(row):
        failed_event = next(
            (
                item
                for item in reversed(sorted(row.events, key=lambda x: (x.created_at, x.id)))
                if item.event_type in {"CALL_FAILED", "VOICE_STREAM_FAILED", "SPEECH_TRANSCRIPTION_FAILED"}
            ),
            None,
        )
        failure_reason = failed_event.payload_json.get("failure_reason") if failed_event else None
        failure_code = (failed_event.payload_json.get("failure_classification") or failed_event.payload_json.get("failure_code")) if failed_event else None
        return {"id": row.id, "provider": row.provider, "provider_mode": row.provider_mode, "status": row.status,
                "scenario": row.scenario, "provider_call_reference": row.provider_call_reference, "outcome_intent": row.outcome_intent,
                "failure_reason": failure_reason, "failure_code": failure_code,
                "created_at": _iso(row.created_at), "turns": [{"id": item.id, "speaker": item.speaker, "text": item.text, "intent": item.intent, "timestamp": _iso(item.timestamp)} for item in sorted(row.turns, key=lambda x: (x.sequence_number, x.id))],
                "events": [_record(item, event_type=item.event_type, source=item.source, timestamp=item.created_at, payload=item.payload_json, provider_mode=item.provider_mode) for item in sorted(row.events, key=lambda x: (x.created_at, x.id))]}

    @staticmethod
    def _escalation(row):
        return {"id": row.id, "status": row.status, "reason": row.escalation_reason, "priority": row.priority,
                "provider_mode": row.provider_mode, "created_at": _iso(row.created_at),
                "events": [_record(item, event_type=item.event_type, source=item.actor, timestamp=item.created_at, payload=item.payload_json) for item in sorted(row.events, key=lambda x: (x.created_at, x.id))]}

    @staticmethod
    def _audit(case):
        entries = []
        for row in case.audit_logs:
            entries.append(_record(row, event_type=row.event_type, source=row.actor, timestamp=row.created_at, payload=row.payload_json))
        for row in case.intervention_events:
            entries.append(_record(row, event_type=row.event_type, source=row.actor, timestamp=row.created_at, payload=row.payload_json))
        for item in case.payment_links:
            for row in item.events:
                entries.append(_record(row, event_type=row.event_type, source=row.source, timestamp=row.occurred_at, payload=row.payload_json, provider_mode=row.provider_mode))
        for item in case.payment_orders:
            for row in item.events:
                entries.append(_record(row, event_type=row.event_type, source=row.source, timestamp=row.occurred_at, payload=row.payload_json, provider_mode=row.provider_mode))
        for item in case.message_attempts:
            for row in item.events:
                entries.append(_record(row, event_type=row.event_type, source="provider", timestamp=row.occurred_at, payload=row.payload_json, provider_mode=row.provider_mode))
        for item in case.escalations:
            for row in item.events:
                entries.append(_record(row, event_type=row.event_type, source=row.actor, timestamp=row.created_at, payload=row.payload_json))
        for intervention in case.interventions:
            for call in intervention.voice_calls:
                for row in call.events:
                    entries.append(_record(row, event_type=row.event_type, source=row.source, timestamp=row.created_at, payload=row.payload_json, provider_mode=row.provider_mode))
        return sorted(entries, key=lambda row: (row["timestamp"] or "", row["event_type"], row["id"]))
