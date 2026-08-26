# Recovery Intelligence

Gate 13 adds a read-only intelligence projection for one persisted
`RecoveryCase`. `RecoveryIntelligenceService` consumes the existing journey
projection, so it has no model, simulator, decision-engine, provider, or
mutation dependency.

## Observable detection

Detection uses only case fields and stored observable facts: failure reason,
payment method, incident flag, decision timestamp, amount in paise, case
status, configured contact window, and any persisted contact history. Severity
is deterministic: `high` for an incident or amount at least 100,000 paise,
`medium` for an amount at least 25,000 paise or a case past `NEW`, otherwise
`low`. These are operational display rules, not risk or causal claims.

## Root-cause language

Failure reasons map to `EXPIRED_PAYMENT_METHOD`, `INSUFFICIENT_FUNDS`,
`ISSUER_DECLINE`, and `CUSTOMER_ABANDONMENT`. `technical_degradation` or an
incident flag produces `TECHNICAL_INCIDENT`; an unrecognized reason produces
`UNKNOWN_OR_OTHER`, or low-confidence `CUSTOMER_INACTION` when prior contact
history exists without a recorded response. Every diagnosis includes evidence
and uncertainty. No latent segment, environment state, or future outcome is
read or returned.

## Decision and outcome intelligence

Decision narrative fields are copied from persisted `Decision` and
`DecisionCandidate` records. Cost, fatigue, constraint, and highest-probability
comparisons come from the stored decision trace; the service never recomputes
them. Outcome status is derived from persisted case/intervention lifecycle,
outcomes, executions, and escalations. Provider acceptance is not recovery;
only the persisted recovery lifecycle can produce `RECOVERED`.

## API and UI boundary

`GET /api/v1/recovery-cases/{case_id}/intelligence` returns the explicit
`RecoveryIntelligenceResponse` schema. It includes detection, diagnosis,
stored decision explanation, intervention/provider state, outcome, a compact
journey summary, stored Gate 6 explanation metadata, and deterministic
descriptive insights. Voice details appear only for a selected
`VOICE_RECOVERY` case with a persisted call. `LOCAL`, `MOCK`, and `TEST` calls
are labeled `Demo Voice Agent`; live language requires a live mode and stored
provider reference.

The Decision Room presents the five-part narrative—problem, root cause,
decision, intervention, outcome—while retaining candidate economics and the
raw persisted audit journey below it. No LLM is called by this endpoint.
