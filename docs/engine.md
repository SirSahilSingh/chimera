# Gate 4 CHIMERA Decision Engine

The engine receives only a `PaymentFailureEvent` and selects the highest
expected-net-value permissible action. It does not call an LLM, execute an
action, or implement persistence/API/frontend behavior.

## Scoring

For every action:

```text
expected_gross_recovery_paise = ROUND_HALF_UP(
  predicted_probability * recoverable_amount_paise
)

expected_net_value_paise = expected_gross_recovery_paise
  - action_cost_paise
  - incentive_cost_paise
  - fatigue_penalty_paise
```

The model probability is read from the compatible Gate 3 artifact. All final
accounting and comparisons use integer paise. Fractional paise use Decimal
`ROUND_HALF_UP`.

Fatigue uses the frozen observable formula:

```text
fatigue_base_paise[action] * (1 + contacts_last_7_days)
```

The trace records the base amount, contact count, multiplier, and resulting
penalty.

## Constraints

- All seven frozen actions are considered.
- Actions unavailable on the event are blocked as `unavailable_action`.
- `SEND_MESSAGE` and `VOICE_RECOVERY` are blocked outside the configured
  contact window as `outside_contact_window`.
- Retries, payment links, escalation, and `DO_NOTHING` remain eligible outside
  the contact window.
- The frozen observable context has no pending-promise field, so the engine
  does not infer promise-to-pay state from hidden truth or an unqualified
  response.

Blocked candidates remain in every decision trace.

## Tie-breaking

If expected net values differ by no more than one paise, choose the lower
customer-friction action, then lower action cost, then the fixed simulator
action order. The friction order is:

`DO_NOTHING`, `RETRY_LATER`, `RETRY_NOW`, `PAYMENT_LINK`, `SEND_MESSAGE`,
`VOICE_RECOVERY`, `ESCALATE`.

## Compatibility and Arena

Engine version: `chimera_engine_v1.0.0`. The engine rejects incompatible model
version, simulator version/configuration hash, or feature schema. The
`ChimeraPolicyAdapter` implements the existing Arena policy interface, so the
approved baselines and CHIMERA receive the same event batches.

Run the Gate 4 development evaluation with:

```powershell
python backend/scripts/run_gate4_arena.py
```
