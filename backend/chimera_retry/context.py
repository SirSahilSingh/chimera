from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class RetryContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intervention_id: str = Field(min_length=1, max_length=36)
    recovery_case_id: str = Field(min_length=1, max_length=36)
    decision_id: str = Field(min_length=1, max_length=36)
    action: str
    amount_paise: StrictInt = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    attempt_number: StrictInt = Field(ge=1)
    idempotency_key: str = Field(min_length=64, max_length=64)


FORBIDDEN_RETRY_FIELDS = frozenset({"customer_segment", "environment_state", "hidden_state", "natural_recovery_probability", "future_outcome", "model_coefficients"})
