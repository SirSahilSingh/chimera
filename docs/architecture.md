# CHIMERA Architecture

## Scope

This document describes the approved implementation direction. Gate 0 is documentation only. The simulator, policies, model, and Arena must run locally before PostgreSQL or frontend work becomes a dependency.

## System shape

CHIMERA uses one Next.js frontend, one FastAPI backend, and PostgreSQL. The backend owns provider calls, model inference, policy enforcement, execution adapters, and audit behavior. No microservices, Redis, Kafka, vector database, RAG, or complex orchestration is required for the MVP.

```text
Simulator / Razorpay webhook
          ↓
    Context builder
          ↓
 Recovery probability model
          ↓
 Expected-value scoring
          ↓
   Policy validation
          ↓
 Deterministic decision
          ↓
 Action adapter / simulator
          ↓
 Outcome and state update
```

## LLM boundary

The LLM is not on the primary decision path and is not called for every event. It is invoked only for ambiguous or unstructured root-cause interpretation, customer-response interpretation, Hinglish voice interactions, and explanations.

The deterministic path must complete when the LLM is unavailable. Any LLM action request is a proposal routed through the same policy engine; the LLM cannot execute a financial or outreach action directly. LLM self-reported confidence is not trusted for safety.

For Gate 6 explanations, the stored `Decision` and `DecisionCandidate` rows are the source of truth. The backend builds an allowlisted intelligence context, calls an optional server-side provider, validates structured output, and persists an append-only explanation record. Provider failures use deterministic fallback text. The explanation layer cannot modify a decision or execution.

## Operator frontend boundary

The Next.js/TypeScript operator frontend under `frontend/` consumes the existing `/api/v1` contracts for the Command Center, Recovery Cases list, and Decision Room. The frontend never calculates or selects recovery actions; it renders stored candidate economics and statuses, requests deterministic decisions from the backend, requests optional Gate 6 explanations, and asks the existing execution endpoint to perform an eligible stored action. Provider credentials, hidden state, future outcomes, and counterfactual truth never cross into frontend payloads.

## Intervention orchestration boundary

Gate 7 introduces `backend/app/interventions/` between stored `Decision` rows
and future provider adapters. `InterventionService` consumes a persisted
decision, copies its selected action, and manages the explicit lifecycle
`CREATED → QUEUED → READY → EXECUTING → AWAITING_OUTCOME → terminal`. It never
calls the Gate 4 engine and cannot substitute an action. Strict approved
execution context schemas expose only observable payment fields and stable
references. Local executors prove the lifecycle without fabricating recovery;
outcomes are a separate append-only boundary. Razorpay, messaging, and voice
providers remain deferred.

## Voice execution boundary

Gate 8 adds `backend/chimera_voice/` for calls attached only to persisted
`VOICE_RECOVERY` interventions. `VoiceService` first uses the Gate 7 execution
boundary, then manages a separate validated call state machine and append-only
voice transcript/event records. A strict `VoiceContext` contains observable
payment context only. Local deterministic scenarios work without credentials;
the optional live HTTP provider is isolated behind `VOICE_*` configuration.
Conversation intents can record customer requests or a pending operational
outcome, but they cannot change the selected action or declare payment recovery.
Razorpay and payment gateway integration are isolated in
`backend/chimera_payments/`. The payment service creates links only from
persisted `PAYMENT_LINK` interventions or validated Gate 8
`SEND_PAYMENT_LINK` intent. Provider webhooks are the only successful-payment
authority; they are signature-verified, amount/currency validated, idempotent,
and append-only in `payment_events`. The local provider uses synthetic
deterministic links and never contacts a payment gateway.

## Local-first implementation gates

1. Gate 0: document decisions and freeze the simulator specification.
2. Gate 1: implement deterministic simulator and synthetic data.
3. Gate 2: implement Retry-All, Rule Engine, ML placeholder, and minimal Arena.
4. Gate 3: implement recovery model and expected-value scoring.
5. Gate 4: implement CHIMERA decision and deterministic policy/guardrail engine.
6. Gate 5: add PostgreSQL persistence, recovery lifecycle, and audit trail.
7. Gate 6: add LLM and voice adapters; voice initially appears in Decision Room.
8. Gate 7: add provider-independent intervention orchestration and outcome boundary.
9. Gate 9: add Razorpay test-mode/webhook and other concrete payment execution providers.
10. Gate 10: run final QA, Arena evaluation, deployment checks, and demo rehearsal.

## Frontend priority

The first-class demo experiences are:

- Command Center: risk, recovered revenue, current actions, and human intervention needs.
- Decision Room: context, root cause, candidate values, policy result, action, outcome, timeline, and embedded voice interaction.
- Recovery Arena: same-batch strategy comparison with recovered revenue, net value, actions, contacts, and violations.

Recovery Queue, Analytics, Policies, and Audit Log are supporting views after these three experiences work.

## Persistence boundary

PostgreSQL becomes authoritative at Gate 5. Before then, the same domain services use in-memory records and deterministic fixtures. All later persisted decisions record policy, model, prompt, simulator, seed, cost, and configuration versions needed for replay and audit.

## Safety invariants

- All money is integer paise internally.
- Every executable action is policy-validated and idempotent.
- Customer opt-out immediately terminates outreach.
- The configurable contact window applies to outbound message, voice, and applicable human outreach only; retries and internal status checks are not contact-window blocked.
- Future timestamps cannot enter model features.
- All demo data and transcripts are synthetic.
- Razorpay and other provider secrets remain backend-only.

## Gate 10 orchestration boundary

`backend/chimera_orchestration/` routes the stored Gate 7 intervention action
to the Gate 8 voice, Gate 9 payment, Gate 10 messaging, retry, or escalation
boundary. It does not select an action. Messaging and retry providers record
external-operation status separately from recovery outcomes; escalation status
is an operator workflow. See `docs/orchestration.md` for local demos and
configuration.

## Gate 11 live provider and journey boundary

Gate 11 adds explicit provider modes (`LOCAL`, `MOCK`, `TEST`, `LIVE`) to
provider operation records. `POST /api/v1/demo/recovery` is a thin composition
of `CaseService`, `InterventionService`, and `RecoveryOrchestrator`; it accepts
only the observable `CaseCreate` contract and never accepts a client-selected
action. `GET /api/v1/recovery-cases/{case_id}/journey` loads persisted records
and returns a chronological, append-only projection without recomputing a
decision. Razorpay, Twilio-compatible messaging, and the optional provider-
neutral voice adapter remain server-side boundaries with bounded timeouts,
signature verification, sanitized event payloads, and idempotent event handling.

## Gate 13 recovery intelligence boundary

`backend/chimera_intelligence/` now includes a read-only
`RecoveryIntelligenceService` alongside the Gate 6 explanation adapter. The
service consumes the persisted journey projection and returns deterministic
detection, observable-only root-cause analysis, stored-decision narrative,
provider/intervention state, outcome status, and descriptive post-outcome
insights. It never invokes the model or decision engine, generates simulator
outcomes, calls an LLM by default, or mutates lifecycle state. The consolidated
endpoint is `GET /api/v1/recovery-cases/{case_id}/intelligence`.
