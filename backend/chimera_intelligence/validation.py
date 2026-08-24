from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from backend.chimera_simulator.models import ACTIONS

from .schemas import SanitizedDecisionContext, StructuredExplanation


class ExplanationValidationError(ValueError):
    def __init__(self, message: str, *, action_mismatch: bool = False) -> None:
        super().__init__(message)
        self.action_mismatch = action_mismatch


_FORBIDDEN_TERMS = (
    "hidden_state",
    "customer_segment",
    "environment_state",
    "natural_recovery_probability",
    "action_responsiveness",
    "action_outcomes",
    "future_outcome",
    "recovery_timestamp",
    "latent variable",
    "simulator truth",
)
_NUMERIC_TEXT = re.compile(r"(?:₹|\bINR\b|\b\d+(?:\.\d+)?\b|%)", re.IGNORECASE)


def _all_text(output: StructuredExplanation) -> str:
    return json.dumps(output.model_dump(mode="json"), sort_keys=True)


def validate_explanation(raw: Any, context: SanitizedDecisionContext) -> StructuredExplanation:
    try:
        output = StructuredExplanation.model_validate(raw)
    except ValidationError as exc:
        raise ExplanationValidationError("structured explanation schema validation failed") from exc
    if output.recommendation.action != context.decision.selected_action:
        raise ExplanationValidationError("recommendation action conflicts with stored selected action", action_mismatch=True)
    allowed_actions = set(ACTIONS)
    if output.recommendation.action not in allowed_actions:
        raise ExplanationValidationError("recommendation action is not a valid CHIMERA action")
    candidate_actions = {candidate.action for candidate in context.candidates}
    for alternative in output.alternatives:
        if alternative.action not in candidate_actions or alternative.action == context.decision.selected_action:
            raise ExplanationValidationError("alternative action is not present in the stored candidate trace")
    text = _all_text(output)
    if _NUMERIC_TEXT.search(text):
        raise ExplanationValidationError("explanation text contains an unvalidated numeric or monetary claim")
    lowered = text.lower()
    if any(term in lowered for term in _FORBIDDEN_TERMS):
        raise ExplanationValidationError("explanation text references forbidden simulator truth")
    return output
