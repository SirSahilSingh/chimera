"""Optional, explanation-only intelligence layer for CHIMERA."""

from .agent import ExplanationAgent, ExplanationResult
from .context import build_intelligence_context
from .schemas import SanitizedDecisionContext, StructuredExplanation

__all__ = [
    "ExplanationAgent",
    "ExplanationResult",
    "SanitizedDecisionContext",
    "StructuredExplanation",
    "build_intelligence_context",
]
