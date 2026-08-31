from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class PaymentContext(BaseModel):
    """The only context a payment provider may receive."""

    model_config = ConfigDict(extra="forbid", strict=True)

    recovery_case_id: str = Field(min_length=1, max_length=36)
    intervention_id: str = Field(min_length=1, max_length=36)
    decision_id: str = Field(min_length=1, max_length=36)
    amount_paise: StrictInt = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str = Field(min_length=1, max_length=255)
    expires_at: datetime | None = None
    customer_email: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
    idempotency_key: str = Field(min_length=64, max_length=64)

    @field_validator("currency")
    @classmethod
    def currency_is_inr(cls, value: str) -> str:
        if value != "INR":
            raise ValueError("only INR is supported")
        return value

    @field_validator("expires_at")
    @classmethod
    def expiry_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return value


class PaymentOrderContext(BaseModel):
    """Merchant-side context for the initial Razorpay Order."""

    model_config = ConfigDict(extra="forbid", strict=True)

    external_reference_id: str = Field(min_length=1, max_length=255)
    customer_id: str = Field(min_length=1, max_length=255)
    amount_paise: StrictInt = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str = Field(min_length=1, max_length=255)
    customer_email: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
    idempotency_key: str = Field(min_length=64, max_length=64)

    @field_validator("currency")
    @classmethod
    def currency_is_inr(cls, value: str) -> str:
        if value != "INR":
            raise ValueError("only INR is supported")
        return value


ALLOWED_CONTEXT_FIELDS = frozenset(PaymentContext.model_fields)
FORBIDDEN_CONTEXT_FIELDS = frozenset({
    "customer_segment", "environment_state", "natural_recovery_probability",
    "action_conditioned_probability", "model_coefficients", "future_outcome",
    "hidden_state", "api_key", "api_secret", "webhook_secret",
})
