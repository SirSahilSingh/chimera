from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt

from backend.chimera_simulator.models import ACTIONS

from .versions import CONTEXT_SCHEMA_VERSION


class ContextCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    payment_amount_paise: StrictInt = Field(ge=0)
    currency: str
    failure_reason: str
    payment_method: str
    incident_flag: StrictBool
    decision_timestamp: datetime
    contact_window_status: str


class ContextDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_action: str
    predicted_probability: StrictFloat = Field(ge=0.0, le=1.0)
    expected_gross_recovery_paise: StrictInt
    expected_net_value_paise: StrictInt


class ContextCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    predicted_probability: StrictFloat = Field(ge=0.0, le=1.0)
    expected_net_value_paise: StrictInt
    action_cost_paise: StrictInt = Field(ge=0)
    fatigue_penalty_paise: StrictInt = Field(ge=0)
    status: str
    blocked_reason: str | None


class ContextDecisionFactors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cost_changed_winner: StrictBool
    fatigue_changed_winner: StrictBool
    constraint_changed_winner: StrictBool
    tie_break_applied: StrictBool


class SanitizedDecisionContext(BaseModel):
    """Strict, allowlisted context supplied to an explanation provider."""

    model_config = ConfigDict(extra="forbid")

    context_schema_version: str = CONTEXT_SCHEMA_VERSION
    case: ContextCase
    decision: ContextDecision
    candidates: list[ContextCandidate]
    decision_factors: ContextDecisionFactors


class ExplanationRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    reason: str = Field(min_length=1, max_length=1000)


class ExplanationKeyFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor: str = Field(min_length=1, max_length=300)
    impact: str = Field(min_length=1, max_length=1000)


class ExplanationAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    reason_not_selected: str = Field(min_length=1, max_length=1000)


class StructuredExplanation(BaseModel):
    """Provider output; deterministic numeric fields are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1500)
    recommendation: ExplanationRecommendation
    key_factors: list[ExplanationKeyFactor] = Field(default_factory=list, max_length=10)
    alternatives: list[ExplanationAlternative] = Field(default_factory=list, max_length=10)
    next_step: str = Field(min_length=1, max_length=1000)
    operator_note: str = Field(min_length=1, max_length=1000)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class ExplanationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    decision_id: str
    recovery_case_id: str
    explanation_source: str
    provider: str
    model_name: str
    prompt_version: str
    explanation_version: str
    input_context_hash: str
    output_hash: str
    generated_at: datetime
    fallback_reason: str | None
    structured_explanation: StructuredExplanation
