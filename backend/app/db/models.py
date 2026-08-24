from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"
    __table_args__ = (UniqueConstraint("external_event_id", name="uq_recovery_cases_external_event_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
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
