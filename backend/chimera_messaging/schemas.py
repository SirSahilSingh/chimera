from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MessageAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    intervention_id: str
    decision_id: str
    provider: str
    idempotency_key: str
    attempt_number: int
    template_key: str
    template_version: str
    rendered_content_hash: str
    provider_message_id: str | None
    status: str
    delivery_state: str
    sent_at: datetime | None
    created_at: datetime
    events: list["MessagingEventResponse"] = []


class MessagingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    message_attempt_id: str
    provider: str
    provider_event_id: str
    event_type: str
    delivery_state: str
    signature_verified: bool
    occurred_at: datetime
    payload_hash: str
    payload_json: dict
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageAttemptResponse]


class RetryStatus(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    AWAITING_OUTCOME = "AWAITING_OUTCOME"


class RetryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    intervention_id: str
    decision_id: str
    action: str
    idempotency_key: str
    attempt_number: int
    provider: str
    provider_reference: str | None
    status: str
    request_hash: str
    result_hash: str | None
    validated_result_json: dict
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class ScheduledRetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    intervention_id: str
    decision_id: str
    idempotency_key: str
    attempt_number: int
    scheduled_at: datetime
    schedule_reason: str
    eligibility_status: str
    execution_status: str
    executed_at: datetime | None
    created_at: datetime


class EscalationStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class EscalationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    escalation_id: str
    event_type: str
    status: str
    actor: str
    payload_json: dict
    sequence_number: int
    created_at: datetime


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    intervention_id: str
    decision_id: str
    escalation_reason: str
    priority: int
    idempotency_key: str
    status: str
    created_at: datetime
    updated_at: datetime
    events: list[EscalationEventResponse] = []


class EscalationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="Automated recovery could not safely proceed", min_length=1, max_length=255)
