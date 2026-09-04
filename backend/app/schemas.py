from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from backend.chimera_simulator.models import ACTIONS, ROOT_CAUSES


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_event_id: str = Field(min_length=1, max_length=255)
    payment_id: str = Field(min_length=1, max_length=255)
    customer_id: str = Field(min_length=1, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
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


class DemoScenario(StrEnum):
    PAYMENT_RECOVERY = "payment_recovery"
    TECHNICAL_RETRY = "technical_retry"
    VOICE_RECOVERY = "voice_recovery"
    ESCALATION = "escalation"


class DemoRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: DemoScenario
    provider_mode: Literal["LOCAL", "MOCK", "TEST", "LIVE"] = "LOCAL"
    customer_phone: str | None = Field(default=None, max_length=32)
    amount_paise: StrictInt | None = Field(default=None, ge=1)
    failure_reason: Literal["issuer_decline", "expired_method", "technical_degradation", "insufficient_funds", "abandonment", "other"] | None = None
    payment_method: Literal["card", "upi", "netbanking"] | None = None

    @property
    def expected_action(self) -> str:
        return {
            DemoScenario.PAYMENT_RECOVERY: "PAYMENT_LINK",
            DemoScenario.TECHNICAL_RETRY: "RETRY_LATER",
            DemoScenario.VOICE_RECOVERY: "VOICE_RECOVERY",
            DemoScenario.ESCALATION: "ESCALATE",
        }[self.scenario]

    def case_payload(self) -> CaseCreate:
        """Return a synthetic, observable-only preset for the deterministic demo."""
        presets = {
            DemoScenario.PAYMENT_RECOVERY: ("expired_method", False, "card", 1000, 10),
            DemoScenario.TECHNICAL_RETRY: ("insufficient_funds", True, "card", 12500, 10),
            DemoScenario.VOICE_RECOVERY: ("insufficient_funds", False, "card", 125000, 10),
            DemoScenario.ESCALATION: ("insufficient_funds", False, "upi", 10000000, 0),
        }
        failure_reason, incident_flag, payment_method, amount_paise, hour = presets[self.scenario]
        token = uuid4().hex
        from datetime import datetime, timezone
        return CaseCreate(
            external_event_id=f"gate14-demo-{self.scenario.value}-{token}",
            payment_id=f"synthetic-payment-{token}",
            customer_id=f"synthetic-customer-{token}",
            amount_paise=self.amount_paise or amount_paise,
            currency="INR",
            failure_reason=self.failure_reason or failure_reason,
            incident_flag=incident_flag,
            payment_method=self.payment_method or payment_method,
            customer_phone=self.customer_phone,
            decision_timestamp=datetime(2026, 8, 26, hour, tzinfo=timezone.utc),
        )


class DemoRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: DemoScenario
    case_id: str
    decision_id: str
    intervention_id: str
    selected_action: str
    current_status: str
    provider: str | None
    provider_mode: str
    provider_mode_label: str
    journey_url: str


class ArenaRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seeds: list[StrictInt] = Field(default_factory=lambda: [400000], min_length=1, max_length=5)
    count_per_seed: StrictInt = Field(default=25, ge=1, le=1000)


class ArenaStrategySummary(BaseModel):
    strategy: str
    policy_name: str
    recovered_revenue_paise: int
    net_value_paise: int
    interventions: int
    policy_violations: int
    recovery_rate: float
    bar_percent: float


class ArenaBatchSummary(BaseModel):
    label: str
    total_events: int
    value_at_risk_paise: int
    seeds: list[int]
    count_per_seed: int


class ArenaResponse(BaseModel):
    batch: ArenaBatchSummary
    rows: list[ArenaStrategySummary]
    methodology: str
    same_event_batch_across_policies: bool
    simulator_version: str
    config_hash: str


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
    provider_mode: str = "LOCAL"
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
    customer_phone: str | None = None
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
    provider_mode: str = "LOCAL"
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
