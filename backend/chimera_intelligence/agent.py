from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .context import context_json
from .fallback import FallbackReason, build_fallback
from .prompts import build_prompt
from .provider import ExplanationProvider, ProviderError
from .schemas import SanitizedDecisionContext, StructuredExplanation
from .validation import ExplanationValidationError, validate_explanation
from .versions import EXPLANATION_VERSION, PROMPT_VERSION


def canonical_hash(value) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExplanationResult:
    structured_explanation: StructuredExplanation
    explanation_source: str
    provider: str
    model_name: str
    prompt_version: str
    explanation_version: str
    input_context_hash: str
    output_hash: str
    fallback_reason: str | None


class ExplanationAgent:
    """Optional explanation orchestration; it has no decision or execution authority."""

    def __init__(self, provider: ExplanationProvider | None = None) -> None:
        self.provider = provider

    def explain(self, context: SanitizedDecisionContext) -> ExplanationResult:
        context_payload = context_json(context)
        input_hash = canonical_hash(context_payload)
        if self.provider is None:
            return self._fallback(context, input_hash, FallbackReason.PROVIDER_NOT_CONFIGURED)
        try:
            raw = self.provider.generate(context_payload, build_prompt(context_payload))
            try:
                output = validate_explanation(raw, context)
            except ExplanationValidationError as exc:
                if not exc.action_mismatch:
                    return self._fallback(context, input_hash, FallbackReason.SCHEMA_VALIDATION_FAILED)
                raw = self.provider.generate(context_payload, build_prompt(context_payload, correction=True))
                try:
                    output = validate_explanation(raw, context)
                except ExplanationValidationError as retry_exc:
                    reason = FallbackReason.ACTION_MISMATCH if retry_exc.action_mismatch else FallbackReason.SCHEMA_VALIDATION_FAILED
                    return self._fallback(context, input_hash, reason)
        except ProviderError as exc:
            return self._fallback(context, input_hash, exc.reason)
        except Exception:
            return self._fallback(context, input_hash, FallbackReason.PROVIDER_UNAVAILABLE)
        return self._result(output, "llm", self.provider.provider_name, self.provider.model_name, input_hash, None)

    def _fallback(self, context, input_hash: str, reason: FallbackReason) -> ExplanationResult:
        output = build_fallback(context, reason)
        return self._result(output, "fallback", "deterministic_fallback", "none", input_hash, reason.value)

    @staticmethod
    def _result(output, source, provider, model_name, input_hash, fallback_reason):
        output_hash = canonical_hash(output.model_dump(mode="json"))
        return ExplanationResult(
            structured_explanation=output,
            explanation_source=source,
            provider=provider,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            explanation_version=EXPLANATION_VERSION,
            input_context_hash=input_hash,
            output_hash=output_hash,
            fallback_reason=fallback_reason,
        )
