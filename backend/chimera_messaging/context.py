from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


class MessagingContext(BaseModel):
    """Strict observable context permitted to a message provider."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intervention_id: str = Field(min_length=1, max_length=36)
    recovery_case_id: str = Field(min_length=1, max_length=36)
    decision_id: str = Field(min_length=1, max_length=36)
    selected_action: str = Field(min_length=1, max_length=32)
    customer_id: str = Field(min_length=1, max_length=255)
    language: str = Field(min_length=2, max_length=16)
    amount_paise: StrictInt = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    payment_method: str = Field(min_length=1, max_length=32)
    failure_reason: str = Field(min_length=1, max_length=64)
    incident_flag: StrictBool
    payment_link: str | None = Field(default=None, max_length=512)


FORBIDDEN_MESSAGE_FIELDS = frozenset({
    "customer_segment", "environment_state", "hidden_state", "natural_recovery_probability",
    "action_conditioned_probability", "model_coefficients", "future_outcome", "costs", "fatigue",
})
