# CHIMERA Recovery Probability Model Card

## Status

Gate 3.5 complete. The original Gate 3 artifact remains preserved as
`recovery_model_v1.0.0`. The selected benchmark candidate is
`recovery_model_v2_interaction_lr.0.0`; it has not replaced the Gate 4
artifact or been evaluated in a new Arena run.

## Intended use

Estimate:

```text
P(recovery within 7 days | observable context, candidate action)
```

The model supports later expected-value comparison. It does not authorize
financial actions, bypass policy validation, or implement CHIMERA's final
decision policy.

## Explicit synthetic-data limitation

> The recovery model is trained and evaluated entirely on synthetic data generated from frozen simulator assumptions. Its purpose is to demonstrate the CHIMERA decision architecture, evaluation methodology, and calibration workflow. It does not claim real-world predictive performance.

## Training methodology

The model is a deterministic NumPy Logistic Regression with L2 regularization
(`l2=0.0001`, maximum 80 Newton iterations). Each event creates one row per
candidate action, with the seven-day simulator recovery outcome as the target.
Platt scaling is fitted once on the validation split and then applied during
inference. No ML model or CHIMERA policy uses Arena seeds for fitting or tuning.

Experiment timestamp: Gate 3 artifact `2026-08-24T13:26:14.112335+00:00`;
Gate 3.5 benchmark timestamp is recorded in
`data/model_benchmark_v1/benchmark_report.json`.

| Split | Seeds | Events | Action rows | Positive rate |
|---|---|---:|---:|---:|
| Training | 100000, 110000, ..., 190000 | 5,000 | 35,000 | 39.67% |
| Validation/calibration | 200000, 210000, 220000 | 1,500 | 10,500 | 39.47% |
| Holdout | 300000, 310000, 320000 | 1,500 | 10,500 | 40.59% |

Simulator version: `simulator_v1.0.0`  
Simulator configuration hash: `cb3153ea4cf9451b724f06e0a9702ab363ccc92d4ebed898b96629e4c6dbe70b`  
Feature schema: `features_v1.0.0` with 44 features.

## Feature categories

The explicit schema includes scaled integer-paise amount, historical payment
ratios, recent contacts, time encodings, incident flag, observable failure
reason, payment method, language and communication preferences, subscription
state, prior channel/response, contact-window eligibility, and one-hot
candidate action. Customer identifiers and synthetic PII are excluded.

Forbidden fields include hidden segment, exact environment state, natural
recovery probability, action-conditioned ground truth probability, simulator
outcomes, recovery timestamps, promise-to-pay verification, and future-only
records. The builder rejects any source timestamp after the decision timestamp.

## Metrics

| Split | ROC-AUC | PR-AUC | Brier score |
|---|---:|---:|---:|
| Training | 0.7139 | 0.5950 | 0.2081 |
| Validation | 0.7092 | 0.5946 | 0.2088 |
| Holdout | 0.7249 | 0.6220 | 0.2056 |

Holdout per-action results:

| Action | ROC-AUC | PR-AUC | Brier |
|---|---:|---:|---:|
| `RETRY_NOW` | 0.7752 | 0.4957 | 0.1557 |
| `RETRY_LATER` | 0.7227 | 0.6014 | 0.2050 |
| `PAYMENT_LINK` | 0.6388 | 0.6265 | 0.2378 |
| `SEND_MESSAGE` | 0.6790 | 0.6258 | 0.2222 |
| `VOICE_RECOVERY` | 0.7238 | 0.6522 | 0.2096 |
| `ESCALATE` | 0.7104 | 0.6723 | 0.2136 |
| `DO_NOTHING` | 0.7363 | 0.6226 | 0.1954 |

## Calibration

Platt scaling was fit on validation logits only. Validation Brier score changed
from `0.208800` before calibration to `0.208767` after calibration. The small
improvement means calibration is useful but limited; the reliability curves in
`data/model_v1/evaluation_report.json` show residual overprediction in several
high-probability bins.

## Gate 3.5 model benchmark and selection

The benchmark compared the preserved baseline, an interaction Logistic
Regression, and a dependency-free NumPy gradient booster over decision
stumps. All candidates used the same observable event context, candidate
action, seed ranges, event-level split isolation, and seven-day labels. The
workflow was training fit → validation Platt calibration → candidate freeze →
one untouched holdout evaluation. Arena performance and action diversity were
not selection criteria.

| Candidate | Holdout ROC-AUC | Holdout PR-AUC | Holdout Brier |
|---|---:|---:|---:|
| Preserved `recovery_model_v1.0.0` | 0.724893 | 0.622047 | 0.205624 |
| `recovery_model_v2_interaction_lr.0.0` | 0.737706 | 0.637621 | 0.201287 |
| `recovery_model_v3_gradient_boosting.0.0` | 0.710801 | 0.594476 | 0.209414 |

The interaction model was selected because it had the lowest untouched-holdout
Brier score, highest holdout PR-AUC, and a smaller training-to-holdout Brier
gap (`0.001000`) than the other candidates. It is an evaluation-based model
selection result, not a claim that CHIMERA will win the Arena.

The interaction schema version is `features_v2.0.0_interaction` with 170
features: the original 44 plus 126 explicit action-conditioned fields. The
fields cover action × failure reason, incident flag, payment method,
communication preference, subscription state, prior response, recent contact
count, and historical recovery ratio. Hidden simulator state, future records,
and outcomes remain rejected.

The tree benchmark used learning rate `0.08`, 24 deterministic stump
estimators, 12 threshold candidates per feature, L2 `0.001`, and fixed seed
metadata `0`. It was selected against no Arena results and is retained as a
transparent fallback benchmark.

## Limitations and known failure modes

- Synthetic outcomes encode the frozen simulator's assumptions, not production behavior.
- The model observes failure reason and incident flag as permitted synthetic observables; production availability and quality would require separate validation.
- `PAYMENT_LINK` and `SEND_MESSAGE` have weaker discrimination than `RETRY_NOW`; action-specific error should be monitored.
- Repeated action rows for one event are counterfactual synthetic examples and are not independent real-world observations.
- Calibration is only mildly improved and should not be treated as production-grade.
- No causal uplift, treatment-effect, regulatory-compliance, or real-world recovery claim is made.

## Compatibility and artifacts

The artifact is rejected when simulator version, simulator configuration hash,
feature schema, or action order is incompatible. Reproducible artifacts and
reports are under `data/model_v1/`; the inference interface is implemented in
`backend/chimera_model/model.py` and `backend/chimera_model/benchmark.py`.
The explicit `Gate4ModelAdapter` presents the selected benchmark model through
the unchanged Gate 4 interface and records the underlying benchmark version.

## Gate 3.5 limitations

- The tree candidate is intentionally simple and should not be treated as a
  mature CatBoost, LightGBM, or XGBoost implementation.
- The selected interaction model still relies on synthetic observables and
  does not estimate causal treatment effects.
- The benchmark's representative scenarios show context-dependent action
  probabilities, but they do not establish real-world calibration.
- No new Arena comparison was run; Gate 4's prior `PAYMENT_LINK` concentration
  remains an observed downstream limitation until separately reviewed.

## Gate 4 v2 re-evaluation

The selected model was evaluated after selection using the unchanged
`chimera_engine_v1.0.0` and the explicit `Gate4ModelAdapter`. The model was
selected before this Arena evaluation. No Arena result was used to select or
tune the model.

On 5,000 development events, CHIMERA selected all seven actions: `PAYMENT_LINK`
51.98%, `RETRY_LATER` 24.92%, `ESCALATE` 8.68%, `VOICE_RECOVERY` 7.26%,
`SEND_MESSAGE` 4.46%, `DO_NOTHING` 1.38%, and `RETRY_NOW` 1.32%. The selected
action differed from the highest raw predicted-probability action on 1,125
events (22.50%). The unchanged engine recorded 313 cost-changed winners, 34
fatigue-changed winners, and 962 constraint-changed winners.

CHIMERA's mean recovery rate was 52.72%, versus 49.08% for
`SIMPLE_RULE_BASED`; mean gross recovered value was ₹67,20,869.16 versus
₹59,82,514.97; mean net recovery value was ₹67,10,382.56 versus
₹59,77,822.57. These are descriptive synthetic Arena results, not claims of
statistical significance or real-world superiority.

The complete report, including per-seed results, grouped action distributions,
reproducibility checks, traces, hashes, and the v1 comparison is at
`data/model_benchmark_v1/gate4_reevaluation_v2_report.json`.
