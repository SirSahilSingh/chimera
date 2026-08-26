# Gate 7 Intervention Lifecycle

Gate 7 is the provider-independent operational layer between a stored CHIMERA
`Decision` and a future execution provider. The decision remains authoritative:
an intervention copies `Decision.selected_action` exactly and never recomputes
the model, expected value, policy result, or candidate ranking.

## Lifecycle

```text
CREATED → QUEUED → READY → EXECUTING → AWAITING_OUTCOME
                                      ├→ RECOVERED
                                      ├→ FAILED
                                      └→ EXPIRED
```

`CANCELLED` is terminal from `CREATED`, `QUEUED`, or `READY`. `DO_NOTHING`
creates an explicit `COMPLETED` operational record with the audit reason
`No intervention selected by deterministic policy`; it never invokes an
executor. Terminal states cannot transition again.

## Idempotency and ordering

Intervention creation uses SHA-256 over the versioned tuple
`decision_id | decision_run_id | selected_action`. The unique key means a
repeated request returns the existing intervention and cannot create another
active record. Execution attempts use SHA-256 over
`intervention_id | attempt_number | action`; a repeated request while awaiting
outcome returns the existing latest attempt. Queue results are ordered by
priority descending, then `created_at` ascending, then stable ID ascending.

## Execution boundary

`ApprovedExecutionContext` is a strict Pydantic allowlist containing only the
intervention, case, decision references, observable payment failure fields,
and configured metadata. Hidden simulator state, future outcomes, model
internals, secrets, and action-substitution fields are rejected. Gate 7 uses
deterministic local executors for retry, payment link, message, voice, and
escalation actions. Acceptance means only that the execution was accepted; it
does not mean payment recovery.

## Outcomes and audit

Outcome records accept `PENDING`, `RECOVERED`, `NOT_RECOVERED`, `FAILED`, or
`EXPIRED`. Amounts are integer paise, non-negative, and cannot exceed the case
amount. Outcome rows and lifecycle events are append-only; terminal outcomes
cannot be overwritten. Intervention events carry a monotonic per-intervention
sequence so operators can reconstruct creation, queueing, execution attempts,
and recovery status without conflating the stored deterministic decision.

No Razorpay, messaging, telephony, or other external provider integration is
implemented in Gate 7. Concrete provider adapters are deferred to Gate 8.
