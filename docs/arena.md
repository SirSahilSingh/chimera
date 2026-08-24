# Gate 2 Recovery Arena

The Arena evaluates deterministic policies against the frozen simulator without
adding a database, service boundary, ML model, or frontend dependency.

## Policy boundary

Every policy implements `choose_action(event)` and receives only a
`PaymentFailureEvent`. The event contains observable information available at
the decision timestamp. `HiddenState`, `SimulatorOutcome`, latent segments,
exact environment state, and action-conditioned ground-truth probabilities are
held by the runner and are never passed to a policy.

The primary baselines are:

- `NO_INTERVENTION`: always `DO_NOTHING`.
- `RETRY_ALL`: choose `RETRY_NOW` unless the observable incident flag is true
  or the failure reason is `technical_degradation`; otherwise choose
  `RETRY_LATER`.
- `SIMPLE_RULE_BASED`: incident -> `RETRY_LATER`; expired method ->
  `PAYMENT_LINK`; abandonment -> `SEND_MESSAGE`; technical degradation or
  insufficient funds -> `RETRY_LATER`; otherwise -> `RETRY_NOW`.

Contact-window violations are measured only for outbound actions. They are
diagnostics and do not block retries or other non-contact actions.

## Evaluation order and artifacts

For each seed, the runner generates one immutable observable event batch and
shares it with every policy. The order is:

`Observable Event -> Policy Action -> Decision Record -> Simulator Outcome -> Metrics`

Each JSON report contains batch hashes, per-seed metrics, and one decision
record per policy/event. Records include an observable-context hash, selected
action, outcome, recovered amount, and paise-denominated costs. INR fields are
display-only conversions.

Metrics include recovery rate, recovered value, action cost, incentive cost,
fatigue penalty, total intervention cost, net recovery value, action counts,
policy violations, and contact-window violations. Multi-seed summaries report
mean, minimum, maximum, and population standard deviation across seed-level
results.

## Local command

Use development seeds only for Gate 2:

```powershell
python backend/scripts/run_baseline_arena.py `
  --split arena_development `
  --seeds 400000 410000 420000 430000 440000 `
  --count-per-seed 1000
```

The default output is `data/simulator_v1/baseline_arena_dev.json`.
