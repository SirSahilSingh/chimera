from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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


class IntelligenceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=255)
    interpretation: str = Field(min_length=1, max_length=500)


class IntelligenceAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=64)
    explanation: str = Field(min_length=1, max_length=500)


class DetectionIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_type: Literal["payment_failure"]
    failure_reason: str
    payment_method: str
    incident_detected: StrictBool
    failure_timestamp: datetime
    amount_at_risk_paise: StrictInt = Field(ge=0)
    contact_window_status: str
    outbound_contact_eligible: StrictBool
    current_recovery_state: str
    severity: Literal["low", "medium", "high"]
    observable_history: dict[str, StrictInt | None] = Field(default_factory=dict)
    summary: str = Field(min_length=1, max_length=500)


class RootCauseIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_cause: str
    confidence: Literal["low", "medium", "high"]
    contributing_factors: list[str] = Field(default_factory=list, max_length=10)
    evidence: list[IntelligenceEvidence] = Field(default_factory=list, max_length=10)
    alternatives: list[IntelligenceAlternative] = Field(default_factory=list, max_length=10)
    statement: str = Field(min_length=1, max_length=500)


class DecisionAlternativeIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    status: str
    predicted_probability: StrictFloat = Field(ge=0.0, le=1.0)
    expected_net_value_paise: StrictInt
    reason_not_selected: str = Field(min_length=1, max_length=500)


class ConstraintIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    reason: str = Field(min_length=1, max_length=255)


class DecisionIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_action: str
    decision_summary: str = Field(min_length=1, max_length=500)
    alternatives: list[DecisionAlternativeIntelligence] = Field(default_factory=list, max_length=10)
    constraints: list[ConstraintIntelligence] = Field(default_factory=list, max_length=10)
    cost_affected: StrictBool
    fatigue_affected: StrictBool
    constraint_affected: StrictBool
    highest_probability_action: str | None
    highest_probability_action_differed: StrictBool


class VoiceIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    status: str
    provider_mode: str
    customer_intent: str | None
    conversation_result: str
    payment_link_requested: StrictBool
    final_intervention_state: str


class InterventionIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str | None
    status: str
    provider_mode: str
    execution_summary: str = Field(min_length=1, max_length=500)
    voice: VoiceIntelligence | None = None


class OutcomeIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["RECOVERED", "NOT_RECOVERED", "PENDING", "EXPIRED", "ESCALATED", "DECLINED", "FAILED"]
    recovered_amount_paise: StrictInt | None = Field(default=None, ge=0)
    outcome_timestamp: datetime | None = None
    time_to_outcome_seconds: StrictInt | None = Field(default=None, ge=0)
    summary: str = Field(min_length=1, max_length=700)
    recovery_path: list[str] = Field(default_factory=list, max_length=20)


class JourneyTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    label: str
    timestamp: datetime | None
    source: str


class JourneySummaryIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stages_completed: list[str] = Field(default_factory=list, max_length=10)
    current_stage: str
    timeline: list[JourneyTimelineItem] = Field(default_factory=list, max_length=100)


class StoredExplanationIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_source: str
    provider: str
    model_name: str
    generated_at: datetime
    fallback_reason: str | None
    summary: str


class OperationalInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str = Field(min_length=1, max_length=500)


class RecoveryIntelligenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    detection: DetectionIntelligence
    diagnosis: RootCauseIntelligence
    decision: DecisionIntelligence | None
    intervention: InterventionIntelligence
    outcome: OutcomeIntelligence
    journey_summary: JourneySummaryIntelligence
    explanation: StoredExplanationIntelligence | None
    insights: list[OperationalInsight] = Field(default_factory=list, max_length=20)
