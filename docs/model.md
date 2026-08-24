# Gate 3 and Gate 3.5 Recovery Probability Models

Gate 3 adds a local, calibrated Logistic Regression model for:

```text
P(recovery within 7 days | observable event context, candidate action)
```

The model uses NumPy only. `features.py` defines the 44-feature schema and
rejects simulator truth records, forbidden hidden fields, and any historical
payment or contact newer than the decision timestamp. Customer identifiers,
names, phone numbers, emails, and simulator outcomes are deliberately omitted.

Contact features are represented as a pair: `candidate_action_is_outbound` and
`candidate_action_contact_window_eligible`. For outbound actions, eligibility
reflects the configured contact window. For non-contact actions, eligibility is
`1` because the contact-window constraint does not apply; the outbound flag is
`0`, making this explicitly “not constrained,” not an outbound contact claim.

## Dataset pipeline

`dataset.py` generates seven action-conditioned rows per observable event. The
simulator outcome is used only as the binary target. The Gate 3 experiment is:

| Split | Seeds | Events/seed | Events | Action rows |
|---|---|---:|---:|---:|
| Training | 100000, 110000, ..., 190000 | 500 | 5,000 | 35,000 |
| Validation/calibration | 200000, 210000, 220000 | 500 | 1,500 | 10,500 |
| Holdout | 300000, 310000, 320000 | 500 | 1,500 | 10,500 |

Arena development and final seeds are rejected by the dataset specification.

## Training and calibration

The classifier is deterministic full-batch Logistic Regression with L2
regularization (`l2=0.0001`, maximum 80 Newton iterations). Platt scaling is
fit once on validation logits and then applied to validation, holdout, and
inference probabilities. Holdout data is not used for fitting or calibration.

`RecoveryProbabilityModel.predict_probability(event, action)` and
`score_actions(event)` are observable-only inference interfaces. Artifacts record
the simulator version, configuration hash, feature-schema version, seed ranges,
counts, hyperparameters, calibration method, and training timestamp.

Artifacts and reports are written under `data/model_v1/` by:

```powershell
python backend/scripts/train_recovery_model.py
```

## Gate 3.5 benchmark

Gate 3.5 preserves `recovery_model_v1.0.0` and benchmarks two additional
models using the same observable event rows and the same fixed split seeds.
No Arena data is used for fitting, calibration, tuning, or selection.

| Candidate | Representation | Artifact |
|---|---|---|
| `baseline_logistic_regression` | 44 v1 features plus one-hot action | `data/model_v1/recovery_model_v1.json` (read-only) |
| `interaction_logistic_regression` | 44 v1 features plus 126 explicit action-context interactions | `data/model_benchmark_v1/recovery_model_v2_interaction_lr.json` |
| `gradient_boosted_stumps` | Same 170 observable features, deterministic NumPy stumps | `data/model_benchmark_v1/recovery_model_v3_gradient_boosting.json` |

The interaction schema is `features_v2.0.0_interaction`. For each action it
adds indicators for failure reason, incident flag, payment method,
communication preference, subscription state, and prior response, plus
action-conditioned `contacts_last_7_days` and `historic_recovery_ratio`.
Numeric interactions retain their deterministic numeric value only for the
candidate action; other action interaction columns are zero.

The tree candidate is a dependency-free gradient booster over decision
stumps: learning rate `0.08`, 24 estimators, 12 quantile threshold candidates
per feature, L2 `0.001`, and fixed seed metadata `0`. It is intentionally a
transparent benchmark rather than a replacement for a mature production tree
library.

Run the frozen benchmark with:

```powershell
python backend/scripts/benchmark_recovery_models.py
```

The protocol is: fit candidates on training only; fit Platt scaling on
validation only; freeze candidates; evaluate holdout once. The selected
candidate is `recovery_model_v2_interaction_lr.0.0`, chosen by minimum
holdout Brier score (`0.201287`), then holdout PR-AUC, generalization gap, and
fixed simplicity order. Its holdout ROC-AUC is `0.737706` and PR-AUC is
`0.637621`. The tree model scored holdout Brier `0.209414`; the preserved
baseline scored `0.205624`.

The selected model can be passed to the unchanged Gate 4 engine through the
explicit `Gate4ModelAdapter`; the adapter preserves Gate 4's expected-value,
cost, fatigue, constraint, tie-breaking, and explanation logic. No new
CHIMERA Arena comparison is part of Gate 3.5.
