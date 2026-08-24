# Gate 6 Intelligence and Explanation Layer

CHIMERA separates decision-making from explanation. The recovery model, expected-value scorer, policy constraints, tie-breaking, and action execution remain deterministic and authoritative. The intelligence layer receives a sanitized stored decision trace and explains it; it cannot select or execute an action.

## Flow

```text
Observable Context
        ↓
Recovery Model
        ↓
Decision Engine
        ↓
Stored Decision Trace
        ↓
Sanitized Intelligence Context
        ↓
LLM Explanation OR Deterministic Fallback
        ↓
Validated Structured Explanation
        ↓
Append-Only Explanation Record
```

The context builder uses an allowlist from `RecoveryCase`, `Decision`, and `DecisionCandidate`. It does not pass simulator truth, latent segments, environment state, future outcomes, action outcomes, recovery timestamps, or hidden probabilities. Monetary and probability fields are available to the provider as trace facts, but the structured output has no deterministic numeric fields and validation rejects numeric or monetary claims in explanation text.

## Provider and failure behavior

The optional provider is an OpenAI-compatible server-side HTTP adapter configured by `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_TIMEOUT_SECONDS`. The key is never returned or persisted. Missing configuration, timeouts, rate limits, invalid JSON, schema failures, action mismatch, and provider outages use the deterministic fallback.

An action mismatch is rejected and retried once with a correction prompt. A second mismatch falls back. Provider retries happen before persistence, so one explicit API request creates exactly one explanation record.

## Validation, versioning, and audit

Prompt, context, and explanation schemas are versioned. Output is strict JSON with summary, recommendation, factors, alternatives, next step, operator note, and limitations. The recommendation must equal the stored selected action; alternatives must come from the stored candidate list. Every record stores source, provider metadata, prompt/explanation versions, canonical input/output SHA-256 hashes, and a controlled fallback reason.

Explanation rows are append-only. Repeated explicit requests create distinct immutable records. Latest ordering is deterministic by `generated_at DESC, id DESC`; history remains available through the API.

## Threat model and limitations

The provider is untrusted and may hallucinate, reveal unsupported claims, or fail. Strict schemas, allowlisted context, forbidden-field checks, numeric-claim rejection, action validation, and deterministic fallback limit those risks. The layer does not prove causal explanations, regulatory compliance, or real-world recovery performance. Existing API authentication is still outside Gate 6 scope.
