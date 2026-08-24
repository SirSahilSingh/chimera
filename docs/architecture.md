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

## Local-first implementation gates

1. Gate 0: document decisions and freeze the simulator specification.
2. Gate 1: implement deterministic simulator and synthetic data.
3. Gate 2: implement Retry-All, Rule Engine, ML placeholder, and minimal Arena.
4. Gate 3: implement recovery model and expected-value scoring.
5. Gate 4: implement CHIMERA decision and deterministic policy/guardrail engine.
6. Gate 5: add PostgreSQL persistence, recovery lifecycle, and audit trail.
7. Gate 6: add LLM and voice adapters; voice initially appears in Decision Room.
8. Gate 7: add Razorpay test-mode/webhook boundary.
9. Gate 8: build Command Center, Decision Room, and Recovery Arena first; add supporting views afterward.
10. Gate 9: run final QA, Arena evaluation, deployment checks, and demo rehearsal.

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
