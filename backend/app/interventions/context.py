from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from backend.chimera_simulator.models import ACTIONS

from .errors import ActionMismatchError, InvalidExecutionContextError


class ApprovedPaymentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    payment_id: str = Field(min_length=1, max_length=255)
    amount_paise: StrictInt = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    failure_reason: str = Field(min_length=1, max_length=64)
    payment_method: str = Field(min_length=1, max_length=32)
    incident_flag: StrictBool
    decision_timestamp: datetime

    @field_validator("decision_timestamp")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("decision_timestamp must include a timezone")
        return value


class ApprovedExecutionContext(BaseModel):
    """The only context a Gate 7 executor may receive."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intervention_id: str = Field(min_length=1, max_length=36)
    recovery_case_id: str = Field(min_length=1, max_length=36)
    decision_id: str = Field(min_length=1, max_length=36)
    action: str
    payment: ApprovedPaymentContext
    execution_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def known_action(cls, value: str) -> str:
        if value not in ACTIONS:
            raise ValueError(f"unknown action: {value}")
        return value

def build_approved_context(intervention) -> ApprovedExecutionContext:
    decision = intervention.decision
    case = intervention.recovery_case
    if decision is None or case is None:
        raise InvalidExecutionContextError("intervention decision context is unavailable")
    if intervention.action != decision.selected_action:
        raise ActionMismatchError("intervention action does not match stored decision")
    # Gate 5's persisted case is the observable execution boundary. Contact
    # eligibility is intentionally absent until a later provider/policy gate.
    decision_timestamp = case.decision_timestamp
    if decision_timestamp.tzinfo is None:
        # SQLite drops timezone metadata; the persisted API contract requires
        # UTC semantics and PostgreSQL preserves the original offset.
        from datetime import timezone

        decision_timestamp = decision_timestamp.replace(tzinfo=timezone.utc)
    return ApprovedExecutionContext(
        intervention_id=intervention.id,
        recovery_case_id=case.id,
        decision_id=decision.id,
        action=intervention.action,
        payment=ApprovedPaymentContext(
            payment_id=case.payment_id,
            amount_paise=case.amount_paise,
            currency=case.currency,
            failure_reason=case.failure_reason,
            payment_method=case.payment_method,
            incident_flag=case.incident_flag,
            decision_timestamp=decision_timestamp,
        ),
        execution_metadata={"source": "gate7_local_executor"},
    )


def context_hash(context: ApprovedExecutionContext) -> str:
    encoded = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
