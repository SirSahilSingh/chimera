from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EscalationStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    intervention_id: str
    decision_id: str
    escalation_reason: str
    context_json: dict
    priority: int
    idempotency_key: str
    status: str
    provider_mode: str = "LOCAL"
    created_at: datetime
    updated_at: datetime
    events: list["EscalationEventResponse"] = []


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


class EscalationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="Automated recovery could not safely proceed", min_length=1, max_length=255)
