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

## Gate 4 v2 re-evaluation

The selected Gate 3.5 model was evaluated through the unchanged engine using
the explicit `Gate4ModelAdapter`. The adapter preserves the existing Gate 4
compatibility surface while delegating feature construction and prediction to
`recovery_model_v2_interaction_lr.0.0` with schema
`features_v2.0.0_interaction`.

Run the exact development re-evaluation with:

```powershell
python backend/scripts/run_gate4_reevaluation_v2.py
```

Configuration is fixed to `arena_development`, seeds `400000, 410000,
420000, 430000, 440000`, 1,000 events per seed, and policies
`NO_INTERVENTION`, `RETRY_ALL`, `SIMPLE_RULE_BASED`, and `CHIMERA`. The
versioned report is `data/model_benchmark_v1/gate4_reevaluation_v2_report.json`.

The run verifies identical event-batch hashes, repeated deterministic
decisions, policy-order independence, and independence from adding or removing
other policies. It also records per-seed policy economics, action
distributions by observable grouping, seven real decision traces, and a
comparison with the original v1 Gate 4 report.

The model was selected before this Arena evaluation. No Arena result was used
to select or tune the model. No simulator, cost, fatigue, constraint,
tie-breaking, expected-value, rounding, explanation, or decision-engine logic
was changed for this re-evaluation.
