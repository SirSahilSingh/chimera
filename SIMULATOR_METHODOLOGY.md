# CHIMERA Simulator Methodology

## Status and freeze rule

This is the Gate 0 specification for `simulator_v1.0.0`. The specification date is 2026-08-24. The executable simulator is not frozen until Gate 1 produces a source-control commit containing the generator, outcome rules, seed derivation, and configuration. Before Gate 2 policy implementation, record the commit SHA and configuration SHA-256 in `DECISIONS.md`.

Once executable ground truth is frozen, any change to hidden-state generation, environment generation, scenario distributions, outcome rules, costs, fatigue penalties, seed derivation, or configuration requires a new simulator version. The change reason must be documented, prior Arena results must remain addressable and must not be silently overwritten, and a change must never be introduced solely to improve CHIMERA's comparative Arena performance.

## Dataset and time model

- Synthetic customers and synthetic contact fields only.
- Default generated dataset: 10,000 events; the configuration may scale to the PRD range of approximately 10,000–50,000.
- Each customer has a 30-day pre-event history window.
- The evaluation horizon is seven days after the decision event.
- The payment event has an `event_timestamp`; the initial synthetic decision timestamp is set equal to that event timestamp. For a later scheduled decision, `decision_timestamp` is the scheduled evaluation time.
- Features are eligible only when their source timestamp is less than or equal to `decision_time`.
- Future outcomes, hidden segments, action deltas, and simulator probabilities are never model features.
- All amounts and costs are integer paise internally.

## Strict seed separation

Seeds are 32-bit integers assigned to disjoint ranges. The split name and seed are stored with every generated event and Arena run.

| Range | Purpose | May be used for final Arena? |
|---|---|---|
| 100,000–199,999 | Model training data generation | No |
| 200,000–299,999 | Model validation/calibration data generation | No |
| 300,000–399,999 | Final model holdout data generation | No |
| 400,000–499,999 | Development and policy-tuning Arena runs | No |
| 900,000–999,999 | Final Arena evaluation | Yes |

Final Arena seeds must not be used for model fitting, calibration, threshold selection, policy tuning, or prompt tuning. Event identity is `simulator_version:split:seed:event_index`; therefore no exact training event can appear in final Arena evaluation. The final report must list the final seed set and prove that the ranges are disjoint.

## Outcome horizon

The outcome window is closed and deterministic:

- `event_timestamp`: time at which the payment failure event occurs.
- `decision_timestamp`: time at which the simulator evaluates the initial recovery decision; for the initial event it equals `event_timestamp`.
- `outcome_horizon`: the half-open interval `[decision_timestamp, decision_timestamp + 7 days)`. Events at or after the upper boundary do not count for that decision.
- `recovered_event`: an event with at least one successful payment recovery inside the horizon. The event is counted once, using the recovered payment amount.
- `unrecovered_event`: an event with no successful recovery inside the horizon, including failed, expired, cancelled, or still-pending cases at the horizon boundary.
- `promise_to_pay`: a structured voice outcome recorded inside the horizon with a valid promised date. It is represented as `PROMISE_TO_PAY_PENDING`, pauses further outreach, and schedules a verification decision when the promised date falls inside the horizon. It is not recovered revenue unless a successful payment occurs before the horizon closes.
- An unclear voice response, invalid promise date, or opt-out is represented as a non-recovery state and follows the PRD's pause/escalate or stop behavior.

The same definitions apply to every strategy so Arena metrics remain comparable.

## Observable event taxonomy

Each event has one controlled root cause: `issuer_decline`, `expired_method`, `technical_degradation`, `insufficient_funds`, `abandonment`, or `other`.

Observable features include amount, payment method, failure reason, event time, prior attempts and outcomes, historical successful-payment ratio, historical recovery behavior, contacts in the previous seven days, previous response, language and communication preference, subscription state, hour/day, and incident flag.

## Hidden customer segments

The generator samples one primary customer segment per customer. These latent segments are independent of environment/system state. The proposed distribution is:

| Segment | Share | Intended hidden behavior |
|---|---:|---|
| `NATURAL_PAYER` | 30% | Often recovers without intervention; extra contact has low value. |
| `TEMPORARY_LIQUIDITY` | 25% | Delayed retry, message, or voice may help later. |
| `EXPIRED_METHOD_TENDENCY` | 25% | Payment link is materially better than repeated retry. |
| `LOW_ENGAGEMENT` | 20% | Repeated outreach has low incremental value. |

Hidden customer variables are the segment, natural-recovery propensity, customer action responsiveness, and future outcome draws. Segment labels are not exposed to Chimera.

## Independent environment/system state

The generator independently samples one environment state for each event. It may coexist with any customer segment:

| Environment state | Proposed share | System behavior |
|---|---:|---|
| `NORMAL` | 85% | No systemic degradation modifier. |
| `GATEWAY_DEGRADATION` | 10% | Immediate retry is less effective; delayed retry is preferred. |
| `ISSUER_NETWORK_DEGRADATION` | 5% | Issuer/network retries are less effective; waiting is preferred. |

Environment state is not a customer segment and must not replace or overwrite customer latent behavior. It is an event/system variable observable through incident and timing signals where the scenario exposes them. When environment state is hidden from a particular scenario, only its permitted observable proxies reach Chimera.

## Conditional root-cause distribution

The following illustrative matrix is used when the environment is `NORMAL`. Each row sums to 100%.

| Segment | Issuer | Expired | Technical | Funds | Abandonment | Other |
|---|---:|---:|---:|---:|---:|---:|
| Natural payer | 35% | 15% | 15% | 15% | 15% | 5% |
| Temporary liquidity | 20% | 10% | 10% | 40% | 15% | 5% |
| Expired method tendency | 10% | 60% | 10% | 5% | 10% | 5% |
| Low engagement | 15% | 10% | 10% | 20% | 40% | 5% |

For `GATEWAY_DEGRADATION`, set `technical_degradation` to 60% and distribute the remaining 40% across the other root causes according to the selected customer's normal-state row after excluding technical degradation. For `ISSUER_NETWORK_DEGRADATION`, set `issuer_decline` to 50% and distribute the remaining 50% across the other root causes according to that row after excluding issuer decline. This creates an environment/root-cause relationship without making the environment state mutually exclusive with the customer segment.

Amount bands are illustrative: 60% ₹500–₹5,000, 30% ₹5,001–₹25,000, and 10% ₹25,001–₹1,00,000. Amounts are sampled in paise within the selected band.

## Action-conditioned outcomes

The canonical simulator action set is `RETRY_NOW`, `RETRY_LATER`, `PAYMENT_LINK`, `SEND_MESSAGE` (PRD `MESSAGE`), `VOICE_RECOVERY` (PRD `VOICE`), `ESCALATE`, and `DO_NOTHING`.

For each event and action:

```text
p_action = clamp(
  p_natural
  + segment_delta[action]
  + root_cause_delta[action]
  + environment_delta[action]
  + timing_modifier,
  0.01,
  0.99
)
```

`p_natural` is the hidden natural-recovery probability. `DO_NOTHING` uses `p_natural`, so its segment, root-cause, and environment adjustments are all zero. The outcome is sampled using a deterministic seed derived from the Arena seed, event ID, and action type. The simulator does not apply Chimera policy decisions when generating potential outcomes.

For `simulator_v1.0.0`, `timing_modifier` is `0.00` for the initial decision. Timing effects are represented by the `RETRY_LATER` action delta and may not be added ad hoc during policy tuning.

All values in the following tables are versioned simulator configuration. The tables define the complete `root_cause × action` and `environment × action` adjustments used by `simulator_v1.0.0`; there are no unlisted outcome modifiers.

Proposed segment action deltas:

| Segment | Retry now | Retry later | Link | Send message | Voice recovery | Escalate | Do nothing |
|---|---:|---:|---:|---:|---:|---:|---:|
| Natural payer | -0.08 | -0.05 | -0.02 | -0.04 | -0.06 | 0.00 | 0.00 |
| Temporary liquidity | 0.05 | 0.15 | 0.08 | 0.10 | 0.18 | 0.10 | 0.00 |
| Expired method tendency | -0.10 | -0.08 | 0.35 | 0.12 | 0.10 | 0.05 | 0.00 |
| Low engagement | -0.06 | -0.05 | 0.02 | -0.08 | -0.10 | 0.05 | 0.00 |

Proposed root-cause deltas:

| Root cause | Retry now | Retry later | Link | Send message | Voice recovery | Escalate | Do nothing |
|---|---:|---:|---:|---:|---:|---:|---:|
| Issuer decline | 0.02 | 0.04 | 0.00 | 0.02 | 0.03 | 0.01 | 0.00 |
| Expired method | -0.15 | -0.12 | 0.10 | 0.02 | 0.03 | 0.00 | 0.00 |
| Technical degradation | -0.10 | 0.15 | 0.00 | 0.02 | 0.02 | 0.02 | 0.00 |
| Insufficient funds | -0.08 | 0.05 | 0.00 | 0.08 | 0.12 | 0.05 | 0.00 |
| Abandonment | -0.03 | -0.02 | 0.05 | 0.10 | 0.06 | 0.03 | 0.00 |
| Other | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Environment action deltas:

| Environment | Retry now | Retry later | Link | Send message | Voice recovery | Escalate | Do nothing |
|---|---:|---:|---:|---:|---:|---:|---:|
| Normal | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Gateway degradation | -0.10 | 0.15 | 0.00 | 0.01 | 0.02 | 0.02 | 0.00 |
| Issuer/network degradation | -0.12 | 0.10 | 0.00 | 0.01 | 0.01 | 0.02 | 0.00 |

The initial natural-recovery probabilities are 0.70, 0.30, 0.20, and 0.10 for natural payer, temporary liquidity, expired method tendency, and low engagement respectively. These values are illustrative assumptions and must be reported with Arena results.

## Costs and fatigue

Proposed default costs, all in paise:

| Action | Action cost | Incentive cost | Fatigue base |
|---|---:|---:|---:|
| Retry now | 500 | 0 | 0 |
| Retry later | 500 | 0 | 0 |
| Payment link | 100 | 0 | 100 |
| Message | 200 | 0 | 200 |
| Voice | 2,500 | 0 | 800 |
| Escalate | 5,000 | 0 | 0 |
| Do nothing | 0 | 0 | 0 |

For customer-contact actions, fatigue penalty is:

```text
fatigue_penalty = fatigue_base × (1 + prior_contacts_in_7_days)
```

No incentives are modeled in `simulator_v1.0.0`; the incentive field remains configurable so later assumptions do not require a schema redesign. These figures are illustrative, not sourced production tariffs.

## Contact-window scope

The configurable merchant/demo contact window applies only to outbound communication actions: `SEND_MESSAGE`, `VOICE_RECOVERY`, and human outreach where applicable. It does not block payment retries, internal status checks, payment-link generation without outbound delivery, or other non-contact actions. The default remains 08:00–19:00 merchant local time for debt-collection-like demo outreach, but the window is configuration, not a universal legal rule.

## Policy-independent defaults for evaluation

The simulator configuration records the PRD demo defaults: maximum retries 3, maximum contacts 2 per seven days, contact window 08:00–19:00 merchant local time, high-value approval threshold 10,000,000 paise, low-confidence threshold 0.60, and voice enabled. Contact-window enforcement is limited to the outbound communication actions defined above.

The simulator generates outcomes independently of whether an action would later be blocked. Policy violations are counted by the policy engine and reported separately.

## Configuration format

The canonical configuration is YAML with this shape:

```yaml
schema_version: 1
simulator_version: simulator_v1.0.0
freeze:
  specification_date: 2026-08-24
  source_commit: required_at_implementation_freeze
  config_sha256: required_at_implementation_freeze
dataset:
  default_events: 10000
  observation_window_days: 30
  evaluation_horizon_days: 7
distributions:
  segments: {}
  environments: {}
  root_causes_by_segment: {}
  amount_bands: []
outcomes:
  natural_recovery_by_segment: {}
  segment_action_delta: {}
  root_cause_action_delta: {}
  environment_action_delta: {}
  timing_modifier: 0.0
costs_paise:
  action: {}
  incentive: {}
  fatigue_base: {}
policy_defaults: {}
seed:
  derivation: simulator_version + split + seed + event_index + action_type
  ranges:
    training: [100000, 199999]
    validation: [200000, 299999]
    holdout: [300000, 399999]
    arena_development: [400000, 499999]
    arena_final: [900000, 999999]
```

The configuration is part of the simulator version. The freeze hash covers the complete file, including segment and environment priors, root-cause distributions, all segment/root-cause/environment action deltas, natural-recovery probabilities, timing modifiers, costs, fatigue, horizon, and seed ranges. It must be copied into every Arena run record or referenced by its SHA-256 hash.
