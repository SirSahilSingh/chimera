# CHIMERA Recovery Probability Model Card

## Status

Gate 3 complete. Model artifact: `recovery_model_v1.0.0`.

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

Experiment timestamp: `2026-08-24T13:26:14.112335+00:00`.

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
`backend/chimera_model/model.py`.
