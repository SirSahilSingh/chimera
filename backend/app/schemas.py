from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from backend.chimera_simulator.models import ACTIONS, ROOT_CAUSES


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_event_id: str = Field(min_length=1, max_length=255)
    payment_id: str = Field(min_length=1, max_length=255)
    customer_id: str = Field(min_length=1, max_length=255)
    amount_paise: StrictInt = Field(ge=0)
    currency: Literal["INR"]
    failure_reason: Literal["issuer_decline", "expired_method", "technical_degradation", "insufficient_funds", "abandonment", "other"]
    incident_flag: StrictBool = False
    payment_method: Literal["card", "upi", "netbanking"]
    decision_timestamp: datetime

    @field_validator("decision_timestamp")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("decision_timestamp must include a timezone")
        return value


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    action: str
    status: str
    blocked_reason: str | None
    predicted_probability: float
    recoverable_amount_paise: int
    expected_gross_recovery_paise: int
    action_cost_paise: int
    incentive_cost_paise: int
    fatigue_penalty_paise: int
    expected_net_value_paise: int
    expected_net_without_action_cost_paise: int
    expected_net_without_fatigue_paise: int
    rank: int | None
    friction_rank: int
    fatigue_reason: str


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    decision_run_id: str
    selected_action: str
    predicted_probability: float
    expected_gross_recovery_paise: int
    expected_net_value_paise: int
    model_version: str
    feature_schema_version: str
    engine_version: str
    simulator_version: str | None
    prompt_version: str | None
    decision_timestamp: datetime
    created_at: datetime
    candidates: list[CandidateResponse] = []
    trace_json: dict[str, Any] = {}


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    decision_id: str
    action: str
    status: str
    idempotency_key: str
    provider_reference: str | None
    error_code: str | None
    error_message: str | None
    response_json: dict[str, Any]
    executed_at: datetime | None
    created_at: datetime


class RecoveryCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    external_event_id: str
    payment_id: str
    customer_id: str
    amount_paise: int
    currency: str
    failure_reason: str
    incident_flag: bool
    payment_method: str
    decision_timestamp: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    latest_decision: DecisionResponse | None = None
    latest_execution: ExecutionResponse | None = None
    audit_count: int = 0


class PaginatedCases(BaseModel):
    items: list[RecoveryCaseResponse]
    page: int
    page_size: int
    total: int


class HealthResponse(BaseModel):
    status: str
    database: str
    model_compatibility: str
    api_environment: str


class InterventionCreateRequest(BaseModel):
    """Intentionally empty: the action is always read from the stored decision."""

    model_config = ConfigDict(extra="forbid")


class InterventionExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    intervention_id: str
    attempt_number: int
    executor_type: str
    status: str
    idempotency_key: str
    provider_reference: str | None
    request_hash: str
    result_hash: str | None
    error_code: str | None
    error_message_safe: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    response_json: dict[str, Any]


class InterventionOutcomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PENDING", "RECOVERED", "NOT_RECOVERED", "FAILED", "EXPIRED"]
    recovered_amount_paise: StrictInt | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    outcome_reference: str | None = Field(default=None, max_length=255)
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=64)

    @field_validator("occurred_at")
    @classmethod
    def outcome_timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class InterventionOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    intervention_id: str
    status: str
    recovered_amount_paise: int | None
    currency: str | None
    outcome_reference: str | None
    occurred_at: datetime
    source: str
    created_at: datetime


class InterventionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    intervention_id: str
    recovery_case_id: str
    decision_id: str
    event_type: str
    actor: str
    payload_json: dict[str, Any]
    sequence_number: int
    created_at: datetime


class InterventionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_case_id: str
    decision_id: str
    action: str
    status: str
    priority: int
    idempotency_key: str
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    lifecycle_version: int
    executions: list[InterventionExecutionResponse] = []
    outcomes: list[InterventionOutcomeResponse] = []
    events: list[InterventionEventResponse] = []
