# Gate 3 Recovery Probability Model

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
