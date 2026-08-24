from __future__ import annotations

import json
from typing import Any

from .versions import PROMPT_VERSION


SYSTEM_PROMPT = """You are CHIMERA's explanation layer, not its decision-maker.
The selected action has already been determined by a deterministic engine.
Do not recommend another action, change any action, probability, amount, cost,
score, ranking, constraint, or policy result. Use only the supplied context.
Do not invent customer or payment facts. Do not infer hidden customer traits or
future outcomes. Do not claim causal certainty, regulatory compliance, legal or
financial advice, or a recovery guarantee. Distinguish supplied facts from
model predictions. Return only the requested JSON object. Do not include digits,
currency symbols, percentages, monetary values, probabilities, or deterministic
scores in the explanation text; refer to them qualitatively instead.
"""


def build_prompt(context: dict[str, Any], *, correction: bool = False) -> str:
    correction_text = (
        " Your previous response conflicted with the deterministic selected action. "
        "Set recommendation.action to the exact selected_action in the context and do not retry a different action."
        if correction
        else ""
    )
    schema = {
        "summary": "short explanation",
        "recommendation": {"action": "exact selected_action", "reason": "why it was selected"},
        "key_factors": [{"factor": "factor from context", "impact": "qualitative impact"}],
        "alternatives": [{"action": "candidate action", "reason_not_selected": "trace-grounded reason"}],
        "next_step": "next operational step",
        "operator_note": "useful operator note",
        "limitations": ["limitations of this explanation"],
    }
    return (
        f"Prompt version: {PROMPT_VERSION}. {correction_text}\n"
        "Return JSON with this exact shape:\n"
        f"{json.dumps(schema, sort_keys=True)}\n"
        "Sanitized decision context:\n"
        f"{json.dumps(context, sort_keys=True, separators=(',', ':'))}"
    )
