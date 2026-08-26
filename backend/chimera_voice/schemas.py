from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, field_validator

from backend.chimera_simulator.models import ACTIONS


class VoiceScenario(StrEnum):
    CUSTOMER_AGREES_TO_PAY = "customer_agrees_to_pay"
    CUSTOMER_REQUESTS_PAYMENT_LINK = "customer_requests_payment_link"
    CUSTOMER_REQUESTS_RETRY_LATER = "customer_requests_retry_later"
    CUSTOMER_ALREADY_PAID = "customer_already_paid"
    CUSTOMER_DECLINES = "customer_declines"
    NO_ANSWER = "no_answer"
    PROVIDER_FAILURE = "provider_failure"


class VoiceIntent(StrEnum):
    PAY_NOW = "PAY_NOW"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    RETRY_LATER = "RETRY_LATER"
    ALREADY_PAID = "ALREADY_PAID"
    DECLINE = "DECLINE"
    WRONG_PERSON = "WRONG_PERSON"
    CALLBACK_REQUEST = "CALLBACK_REQUEST"
    QUESTION = "QUESTION"
    UNKNOWN = "UNKNOWN"


class VoiceContext(BaseModel):
    """Strict, conversation-only context; decision truth is not included."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intervention_id: str = Field(min_length=1, max_length=36)
    recovery_case_id: str = Field(min_length=1, max_length=36)
    decision_id: str = Field(min_length=1, max_length=36)
    selected_action: Literal["VOICE_RECOVERY"]
    payment_amount_paise: StrictInt = Field(ge=0)
    currency: Literal["INR"]
    failure_reason: str = Field(min_length=1, max_length=64)
    payment_method: str = Field(min_length=1, max_length=32)
    incident_flag: StrictBool
    allowed_recovery_options: tuple[str, ...]
    payment_link: str | None = None


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    speaker: Literal["agent", "customer"]
    text: str = Field(min_length=1, max_length=2000)
    intent: VoiceIntent | None = None
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    requested_action: Literal["RETRY_NOW", "RETRY_LATER", "PAYMENT_LINK"] | None = None
    requires_confirmation: StrictBool
    timestamp: datetime
    validated: StrictBool

    @field_validator("timestamp")
    @classmethod
    def timestamp_timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("voice turn timestamp must include a timezone")
        return value


class VoiceStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: VoiceScenario = VoiceScenario.CUSTOMER_AGREES_TO_PAY


class VoiceDemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: VoiceScenario = VoiceScenario.CUSTOMER_AGREES_TO_PAY


class VoiceWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    provider_call_reference: str = Field(min_length=1, max_length=255)
    event_type: Literal["call_initiated", "ringing", "connected", "conversation", "awaiting_resolution", "completed", "declined", "no_answer", "failed", "cancelled"]
    event_timestamp: datetime
    signature: str = Field(min_length=1, max_length=128)

    @field_validator("event_timestamp")
    @classmethod
    def event_timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("event_timestamp must include a timezone")
        return value


class VoiceTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    call_id: str
    sequence_number: int
    speaker: str
    text: str
    intent: str | None
    confidence: float
    requested_action: str | None
    requires_confirmation: bool
    timestamp: datetime
    validated: bool
    created_at: datetime


class VoiceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    call_id: str
    event_id: str
    event_type: str
    source: str
    provider_mode: str = "LOCAL"
    payload_json: dict
    provider_event_hash: str | None = None
    input_hash: str | None
    transcript_hash: str | None
    voice_agent_version: str
    prompt_version: str
    sequence_number: int
    created_at: datetime


class VoiceCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    intervention_id: str
    recovery_case_id: str
    provider: str
    provider_mode: str = "LOCAL"
    provider_call_reference: str | None
    status: str
    scenario: str
    idempotency_key: str
    input_hash: str
    transcript_hash: str
    voice_agent_version: str
    prompt_version: str
    outcome_intent: str | None
    payment_link: str | None
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    lifecycle_version: int
    turns: list[VoiceTurnResponse] = []
    events: list[VoiceEventResponse] = []


class VoiceHistoryResponse(BaseModel):
    call: VoiceCallResponse
    turns: list[VoiceTurnResponse]
    events: list[VoiceEventResponse]
