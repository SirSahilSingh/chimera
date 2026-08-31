from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class LearningReport(Base):
    """Immutable, versioned learning snapshot; never used by decisioning."""

    __tablename__ = "learning_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    baseline_window: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_window: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    structured_report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ProviderVerification(Base):
    """Append-only safe provider readiness and verification record."""

    __tablename__ = "provider_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    readiness_status: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_result: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_APPLICABLE")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"
    __table_args__ = (UniqueConstraint("external_event_id", name="uq_recovery_cases_external_event_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    failure_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    incident_flag: Mapped[bool] = mapped_column(nullable=False, default=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    decisions: Mapped[list[Decision]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    executions: Mapped[list[ActionExecution]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    explanations: Mapped[list[Explanation]] = relationship(back_populates="recovery_case")
    interventions: Mapped[list[Intervention]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    intervention_events: Mapped[list[InterventionEvent]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    payment_links: Mapped[list[PaymentLink]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    message_attempts: Mapped[list[MessageAttempt]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    retry_attempts: Mapped[list[RetryAttempt]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    scheduled_retries: Mapped[list[ScheduledRetry]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")
    escalations: Mapped[list[Escalation]] = relationship(back_populates="recovery_case", cascade="all, delete-orphan")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    decision_run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    selected_action: Mapped[str] = mapped_column(String(32), nullable=False)
    predicted_probability: Mapped[float] = mapped_column(nullable=False)
    expected_gross_recovery_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_net_value_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(128), nullable=False)
    simulator_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    trace_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="decisions")
    candidates: Mapped[list[DecisionCandidate]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    executions: Mapped[list[ActionExecution]] = relationship(back_populates="decision")
    explanations: Mapped[list[Explanation]] = relationship(back_populates="decision")
    interventions: Mapped[list[Intervention]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    payment_links: Mapped[list[PaymentLink]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    message_attempts: Mapped[list[MessageAttempt]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    retry_attempts: Mapped[list[RetryAttempt]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    scheduled_retries: Mapped[list[ScheduledRetry]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    escalations: Mapped[list[Escalation]] = relationship(back_populates="decision", cascade="all, delete-orphan")


class DecisionCandidate(Base):
    __tablename__ = "decision_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicted_probability: Mapped[float] = mapped_column(nullable=False)
    recoverable_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_gross_recovery_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    action_cost_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    incentive_cost_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    fatigue_penalty_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_net_value_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_net_without_action_cost_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_net_without_fatigue_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    friction_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    fatigue_reason: Mapped[str] = mapped_column(Text, nullable=False)

    decision: Mapped[Decision] = relationship(back_populates="candidates")


class ActionExecution(Base):
    __tablename__ = "action_executions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_action_executions_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="executions")
    decision: Mapped[Decision] = relationship(back_populates="executions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_cases.id"), nullable=True, index=True)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase | None] = relationship(back_populates="audit_logs")


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    explanation_source: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    structured_explanation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="explanations")
    decision: Mapped[Decision] = relationship(back_populates="explanations")


class Intervention(Base):
    """Operational record for carrying out one immutable stored decision."""

    __tablename__ = "interventions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_interventions_idempotency_key"),
        UniqueConstraint("decision_id", name="uq_interventions_decision_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="CREATED")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    lifecycle_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="interventions")
    decision: Mapped[Decision] = relationship(back_populates="interventions")
    executions: Mapped[list[InterventionExecution]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    events: Mapped[list[InterventionEvent]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    outcomes: Mapped[list[InterventionOutcome]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    voice_calls: Mapped[list[VoiceCall]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    payment_links: Mapped[list[PaymentLink]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    message_attempts: Mapped[list[MessageAttempt]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    retry_attempts: Mapped[list[RetryAttempt]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    scheduled_retries: Mapped[list[ScheduledRetry]] = relationship(back_populates="intervention", cascade="all, delete-orphan")
    escalations: Mapped[list[Escalation]] = relationship(back_populates="intervention", cascade="all, delete-orphan")


class InterventionExecution(Base):
    """Append-only record of one local/provider execution attempt."""

    __tablename__ = "intervention_executions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_intervention_executions_idempotency_key"),
        UniqueConstraint("intervention_id", "attempt_number", name="uq_intervention_executions_attempt"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    executor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    intervention: Mapped[Intervention] = relationship(back_populates="executions")


class InterventionEvent(Base):
    """Append-only intervention lifecycle audit event."""

    __tablename__ = "intervention_events"
    __table_args__ = (UniqueConstraint("intervention_id", "sequence_number", name="uq_intervention_events_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    intervention: Mapped[Intervention] = relationship(back_populates="events")
    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="intervention_events")


class InterventionOutcome(Base):
    """Append-only outcome observations; terminal outcomes are never overwritten."""

    __tablename__ = "intervention_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    recovered_amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    outcome_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    intervention: Mapped[Intervention] = relationship(back_populates="outcomes")


class VoiceCall(Base):
    """Mutable lifecycle pointer with append-only turns and events."""

    __tablename__ = "voice_calls"
    __table_args__ = (
        UniqueConstraint("intervention_id", name="uq_voice_calls_intervention_id"),
        UniqueConstraint("idempotency_key", name="uq_voice_calls_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    provider_call_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    transcript_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    voice_agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome_intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    lifecycle_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    intervention: Mapped[Intervention] = relationship(back_populates="voice_calls")
    turns: Mapped[list[VoiceTurn]] = relationship(back_populates="call", cascade="all, delete-orphan")
    events: Mapped[list[VoiceEvent]] = relationship(back_populates="call", cascade="all, delete-orphan")


class VoiceTurn(Base):
    """Append-only validated conversation turn."""

    __tablename__ = "voice_turns"
    __table_args__ = (UniqueConstraint("call_id", "sequence_number", name="uq_voice_turns_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    call_id: Mapped[str] = mapped_column(ForeignKey("voice_calls.id"), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False)
    requested_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requires_confirmation: Mapped[bool] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    validated: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    call: Mapped[VoiceCall] = relationship(back_populates="turns")


class VoiceEvent(Base):
    """Append-only voice lifecycle/provider audit event."""

    __tablename__ = "voice_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_voice_events_event_id"),
        UniqueConstraint("call_id", "sequence_number", name="uq_voice_events_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    call_id: Mapped[str] = mapped_column(ForeignKey("voice_calls.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provider_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    voice_agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    call: Mapped[VoiceCall] = relationship(back_populates="events")


class PaymentLink(Base):
    """Mutable provider-link pointer; provider events remain append-only below."""

    __tablename__ = "payment_links"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payment_links_idempotency_key"),
        UniqueConstraint("provider", "provider_payment_link_id", name="uq_payment_links_provider_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    provider_payment_link_id: Mapped[str] = mapped_column(String(255), nullable=False)
    short_url: Mapped[str] = mapped_column(String(512), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="CREATED")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="payment_links")
    intervention: Mapped[Intervention] = relationship(back_populates="payment_links")
    decision: Mapped[Decision] = relationship(back_populates="payment_links")
    attempts: Mapped[list[PaymentAttempt]] = relationship(back_populates="payment_link", cascade="all, delete-orphan")
    events: Mapped[list[PaymentEvent]] = relationship(back_populates="payment_link", cascade="all, delete-orphan")


class PaymentAttempt(Base):
    """Provider payment reference and status observed for a payment link."""

    __tablename__ = "payment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payment_link_id: Mapped[str] = mapped_column(ForeignKey("payment_links.id"), nullable=False, index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    payment_link: Mapped[PaymentLink] = relationship(back_populates="attempts")
    events: Mapped[list[PaymentEvent]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class PaymentEvent(Base):
    """Append-only, sanitized provider/reconciliation event."""

    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payment_link_id: Mapped[str] = mapped_column(ForeignKey("payment_links.id"), nullable=False, index=True)
    payment_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("payment_attempts.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    signature_verified: Mapped[bool] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    payment_link: Mapped[PaymentLink] = relationship(back_populates="events")
    attempt: Mapped[PaymentAttempt | None] = relationship(back_populates="events")


class MessageAttempt(Base):
    """One provider send request; rendered content is represented by a hash."""

    __tablename__ = "message_attempts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_message_attempts_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rendered_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(32), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="message_attempts")
    intervention: Mapped[Intervention] = relationship(back_populates="message_attempts")
    decision: Mapped[Decision] = relationship(back_populates="message_attempts")
    events: Mapped[list[MessagingEvent]] = relationship(back_populates="message_attempt", cascade="all, delete-orphan")


class MessagingEvent(Base):
    """Append-only delivery/provider event."""

    __tablename__ = "messaging_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_messaging_events_provider_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_attempt_id: Mapped[str] = mapped_column(ForeignKey("message_attempts.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(32), nullable=False)
    signature_verified: Mapped[bool] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    message_attempt: Mapped[MessageAttempt] = relationship(back_populates="events")


class RetryAttempt(Base):
    """Append-only retry operation; acceptance is not payment recovery."""

    __tablename__ = "retry_attempts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_retry_attempts_idempotency_key"), UniqueConstraint("intervention_id", "attempt_number", name="uq_retry_attempts_intervention_attempt"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validated_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="retry_attempts")
    intervention: Mapped[Intervention] = relationship(back_populates="retry_attempts")
    decision: Mapped[Decision] = relationship(back_populates="retry_attempts")


class ScheduledRetry(Base):
    """Deterministic retry schedule, separate from execution attempts."""

    __tablename__ = "scheduled_retries"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_scheduled_retries_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    schedule_reason: Mapped[str] = mapped_column(String(128), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="scheduled_retries")
    intervention: Mapped[Intervention] = relationship(back_populates="scheduled_retries")
    decision: Mapped[Decision] = relationship(back_populates="scheduled_retries")


class Escalation(Base):
    """Mutable current pointer with append-only status events."""

    __tablename__ = "escalations"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_escalations_idempotency_key"), UniqueConstraint("intervention_id", name="uq_escalations_intervention_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False, index=True)
    intervention_id: Mapped[str] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    escalation_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="escalations")
    intervention: Mapped[Intervention] = relationship(back_populates="escalations")
    decision: Mapped[Decision] = relationship(back_populates="escalations")
    events: Mapped[list[EscalationEvent]] = relationship(back_populates="escalation", cascade="all, delete-orphan")


class EscalationEvent(Base):
    """Append-only escalation status/context event."""

    __tablename__ = "escalation_events"
    __table_args__ = (UniqueConstraint("escalation_id", "sequence_number", name="uq_escalation_events_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    escalation_id: Mapped[str] = mapped_column(ForeignKey("escalations.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    escalation: Mapped[Escalation] = relationship(back_populates="events")
