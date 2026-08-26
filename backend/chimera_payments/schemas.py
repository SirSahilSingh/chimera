from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class PaymentDemoScenario(StrEnum):
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_EXPIRED = "payment_expired"
    PAYMENT_FAILED = "payment_failed"
    DUPLICATE_WEBHOOK = "duplicate_webhook"
    INVALID_WEBHOOK = "invalid_webhook"
    OUT_OF_ORDER_EVENT = "out_of_order_event"


class PaymentWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    provider_event_id: str = Field(min_length=1, max_length=255)
    provider_payment_link_id: str = Field(min_length=1, max_length=255)
    provider_payment_id: str | None = Field(default=None, max_length=255)
    event_type: str = Field(min_length=1, max_length=64)
    status: PaymentStatus
    amount_paise: StrictInt = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def timestamp_timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class PaymentDemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: PaymentDemoScenario = PaymentDemoScenario.PAYMENT_SUCCESS


class PaymentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    payment_link_id: str
    payment_attempt_id: str | None
    provider: str
    provider_mode: str = "LOCAL"
    provider_event_id: str
    event_type: str
    status: str
    amount_paise: int
    currency: str
    signature_verified: bool
    source: str
    occurred_at: datetime
    payload_hash: str
    payload_json: dict
    created_at: datetime


class PaymentAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    payment_link_id: str
    provider_payment_id: str | None
    amount_paise: int
    currency: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime


class PaymentLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recovery_case_id: str
    intervention_id: str
    decision_id: str
    provider: str
    provider_mode: str = "LOCAL"
    provider_payment_link_id: str
    short_url: str
    amount_paise: int
    currency: str
    status: str
    idempotency_key: str
    request_hash: str
    result_hash: str
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: list[PaymentAttemptResponse] = []
    events: list[PaymentEventResponse] = []


class PaymentListResponse(BaseModel):
    items: list[PaymentLinkResponse]
