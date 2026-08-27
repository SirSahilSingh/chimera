# CHIMERA Decision Log

Status: Gate 2 implementation complete. `simulator_v1.0.0` remains frozen; Gate 2 contains only deterministic baseline policies and local Arena evaluation.

## D-001 — Intelligence-first implementation order

Decision: Build the simulator, baseline policies, model, scoring, and deterministic decision flow before PostgreSQL or frontend work.

Date: 2026-08-24

Context: The core product claim is the quality and safety of the recovery decision, not persistence or UI infrastructure.

Chosen approach: Follow Gates 0–4 with local, in-memory execution before Gate 5 persistence.

Alternatives considered: Start with database schema or frontend screens.

Why this approach: It keeps the core intelligence runnable and testable by itself within the 31 August build lock.

Trade-offs: Early runs will not have durable audit or replay records.

Version/affected component: `simulator_v1.0.0`, local Arena, decision engine.

## D-002 — Simulator version and freeze protocol

Decision: The first ground-truth release is named `simulator_v1.0.0`.

Date: 2026-08-24

Context: The PRD requires simulator rules, hidden-state generation, and scenario distributions to precede Chimera scoring and policy logic.

Chosen approach: Freeze the specification now; implement the simulator in Gate 1; then create one source-control commit containing the simulator and configuration before writing policy/scoring code. Record the commit SHA, configuration SHA-256, seed policy, freeze timestamp, and version in this file and every Arena run. After that freeze, changes require a new simulator version, a documented reason, preserved prior results, and a new comparison series; no frozen rule may be changed solely to improve CHIMERA's comparative Arena performance.

Alternatives considered: Tune the simulator and policy together; freeze only the generated dataset.

Why this approach: Freezing the generator and rules protects evaluation integrity and permits unseen-seed evaluation.

Trade-offs: Later changes require `simulator_v1.1.0` or a new version and invalidate direct comparisons.

Version/affected component: `simulator_v1.0.0`, `SIMULATOR_METHODOLOGY.md`.

## D-003 — Synthetic-only data

Decision: All customers, payment history, contact fields, transcripts, and outcomes are generated.

Date: 2026-08-24

Context: The PRD prohibits unapproved real data and requires synthetic PII.

Chosen approach: Generate observable histories and hidden behavioral state from seeded configuration. No real customer PII is imported.

Alternatives considered: Scrape or import historical merchant data.

Why this approach: It is safe, reproducible, and sufficient for demonstrating the architecture.

Trade-offs: Results cannot establish real-world predictive performance.

Version/affected component: Dataset generator, `MODEL_CARD.md`, README.

## D-004 — Customer behavioral segments

Decision: Use four customer latent segments: `NATURAL_PAYER`, `TEMPORARY_LIQUIDITY`, `EXPIRED_METHOD_TENDENCY`, and `LOW_ENGAGEMENT`. Model `NORMAL`, `GATEWAY_DEGRADATION`, and `ISSUER_NETWORK_DEGRADATION` as independent environment/system states.

Date: 2026-08-24

Context: Customer behavior and gateway/issuer degradation are different causal factors and must be able to coexist.

Chosen approach: Sample one primary customer segment per customer using proposed priors of 30%, 25%, 25%, and 20%. Independently sample an event environment state using proposed priors of 85% normal, 10% gateway degradation, and 5% issuer/network degradation.

Alternatives considered: Make gateway degradation a customer segment; use only failure reason; use an unconstrained continuous latent variable.

Why this approach: Named segments make the synthetic assumptions explainable while remaining hidden from Chimera.

Trade-offs: Named states simplify real heterogeneity and can make the simulator easier to game if exposed; the environment state must remain independent even when it changes root-cause frequencies.

Version/affected component: `simulator_v1.0.0` hidden-state generator.

## D-005 — Hidden and observable variables

Decision: Hidden variables control outcome generation; only event-time observables reach the model.

Date: 2026-08-24

Context: The PRD requires hidden behavioral attributes and a strict temporal cutoff.

Chosen approach: Hidden customer variables: primary segment, natural-recovery propensity, action responsiveness, and simulated future outcome draws. Hidden or scenario-dependent system variable: environment state. Observable: amount, method, failure reason, event timestamp, prior attempts, prior outcomes, prior contacts, prior responses, customer language/preference, subscription state, hour/day, and permitted incident/system signals.

Alternatives considered: Expose segment labels or future outcome probabilities as model features.

Why this approach: It preserves the simulator's counterfactual ground truth while preventing label leakage.

Trade-offs: The model sees imperfect proxies and may not recover the simulator's full hidden state.

Version/affected component: Context builder, model dataset builder, temporal-cutoff tests.

## D-006 — Scenario distributions

Decision: Use an illustrative, versioned distribution for the first synthetic release.

Date: 2026-08-24

Context: The PRD requires controlled root-cause scenarios and realistic correlations but provides no percentages.

Chosen approach: Root causes are sampled conditionally by segment using the matrix in `SIMULATOR_METHODOLOGY.md`. Amount bands are 60% ₹500–₹5,000, 30% ₹5,001–₹25,000, and 10% ₹25,001–₹1,00,000. Use a 30-day pre-event history window and a seven-day outcome horizon.

Alternatives considered: Uniform root causes and amounts; use the PRD's placeholder Arena values as ground truth.

Why this approach: Conditional sampling creates visible but controlled relationships and avoids hardcoded demo results.

Trade-offs: These percentages are illustrative assumptions, not merchant forecasts; changing them requires a simulator version change.

Version/affected component: `simulator_v1.0.0`, Arena methodology.

## D-007 — Action-conditioned outcome rules

Decision: Generate natural recovery and intervention outcomes from a transparent probability function using segment and root-cause deltas.

Date: 2026-08-24

Context: The Arena must compare intervention recovery with natural recovery under frozen ground truth.

Chosen approach: `p_action = clamp(p_natural + segment_delta[action] + root_cause_delta[action] + environment_delta[action] + timing_modifier, 0.01, 0.99)`. The complete root-cause/action and environment/action tables are versioned in `SIMULATOR_METHODOLOGY.md`. Sample one Bernoulli outcome for each evaluated action using the split, seed, event index, and action type. `DO_NOTHING` uses natural recovery. Policy violations are not rewritten as successful outcomes; they are measured separately.

Alternatives considered: Let the policy define outcomes; use a black-box learned simulator.

Why this approach: It is inspectable, reproducible, and independent of Chimera's decision logic.

Trade-offs: It is not a causal model of production behavior and may underrepresent complex interactions.

Version/affected component: `simulator_v1.0.0`, `SIMULATOR_METHODOLOGY.md`.

## D-008 — Cost, incentive, and fatigue assumptions

Decision: Store all costs in paise and treat defaults as illustrative.

Date: 2026-08-24

Context: Expected net value must account for action cost, incentive cost, fatigue, and risk/policy penalty.

Chosen approach: Proposed action costs: retry-now ₹5, retry-later ₹5, payment-link ₹1, message ₹2, voice ₹25, escalate ₹50, do-nothing ₹0. Incentive cost is ₹0 for `simulator_v1.0.0` because no incentive workflow is in MVP. Fatigue is ₹1 per payment-link contact, ₹2 per message, and ₹8 per voice contact, multiplied by `1 + prior_contacts_in_7_days`.

Alternatives considered: Claim production tariffs; omit cost and optimize recovery rate only.

Why this approach: Relative costs make unnecessary outreach visible without pretending to have sourced tariffs.

Trade-offs: Results are sensitive to these assumptions. Every value must remain in the versioned configuration and be disclosed in evaluation output.

Version/affected component: Expected-value scorer, simulator config, Arena report.

## D-009 — Model claim limitation

Decision: The recovery model is an architecture demonstration, not a production performance claim.

Date: 2026-08-24

Context: Synthetic outcomes are generated from the simulator assumptions.

Chosen approach: Use the exact limitation in `MODEL_CARD.md` and `README`.

Alternatives considered: Present synthetic metrics as merchant lift.

Why this approach: It accurately describes the evidence and avoids overstating causal or predictive validity.

Trade-offs: The demo demonstrates workflow, calibration, and evaluation discipline rather than real-world accuracy.

Version/affected component: Model card, README, Arena report.

## D-010 — No LLM on the primary decision path

Decision: LLM calls are optional and event-selective.

Date: 2026-08-24

Context: The approved modification requires deterministic operation when the LLM is unavailable.

Chosen approach: Primary path is context → model → expected value → policy → deterministic decision → action. Invoke the LLM only for ambiguous root-cause interpretation, customer-response interpretation, Hinglish voice, or explanations.

Alternatives considered: Call the LLM for every event and let it choose the action.

Why this approach: It reduces latency/cost and makes financial behavior deterministic and testable.

Trade-offs: Some cases will have less narrative context; the product's core action choice remains explainable.

Version/affected component: Decision engine, LLM adapter, frontend Decision Room.

## D-011 — Arena comparison protocol

Decision: Final Arena results use at least five independent seeds and identical simulator configurations.

Date: 2026-08-24

Context: The PRD requires multi-seed results and warns against self-biased simulation.

Chosen approach: Run deterministic strategies on the full batch. Use a fixed stratified 100–200 event subset or cached outputs for LLM-dependent strategies, and disclose the sampling method.

Alternatives considered: One seed; one live LLM call per event.

Why this approach: It balances reproducibility, comparability, and local runtime limits.

Trade-offs: LLM metrics require a clearly labeled subset comparison rather than an unqualified full-batch comparison.

Version/affected component: Arena runner, evaluation report.

## D-012 — Contact-window and communication assumptions

Decision: Use 08:00–19:00 merchant-local time as the simulator and demo default for debt-collection-like outreach, with communication preference/consent as an explicit input.

Date: 2026-08-24

Context: The PRD grounds this demo default in RBI recovery-agent guidance and references TRAI TCCCPR/NCPR/DND concepts.

Chosen approach: Block voice, SMS, and message actions outside the configured window and when preference/consent disallows the channel. Present the window as a demo control for debt-collection-like flows, not as a universal legal rule or full telecom compliance implementation.

Alternatives considered: Treat the default as universal law; omit communication preference from the simulator.

Why this approach: It demonstrates safety behavior while preserving the PRD's regulatory qualification.

Trade-offs: Exact production compliance remains an implementation dependency and requires legal/provider review.

Version/affected component: Simulator defaults, policy engine, README, Arena methodology.

## D-013 — LLM fallback and authority

Decision: The deterministic model/scoring/policy path is authoritative and must complete without an LLM.

Date: 2026-08-24

Context: The approved flow removes the LLM from the per-event primary path.

Chosen approach: Invoke the LLM only for ambiguous interpretation, customer-response interpretation, Hinglish voice, or explanations. On timeout, rate limit, invalid schema, or provider outage, continue with the deterministic decision and record `llm_fallback` and the failure reason.

Alternatives considered: Require an LLM response before every action; allow an LLM tool call to execute directly.

Why this approach: Financial actions remain deterministic, policy-validated, and available during provider failure.

Trade-offs: Some events will have no LLM-generated narrative; provider-specific behavior remains outside the decision core.

Version/affected component: Decision engine, LLM adapter, audit record.

## D-014 — Model selection and validation

Decision: Start with calibrated Logistic Regression and use XGBoost only as an optional comparison if time permits.

Date: 2026-08-24

Context: The PRD requires one interpretable baseline, time-aware validation, discrimination metrics, calibration, and leakage controls.

Chosen approach: Use an earlier-event training split and later-event holdout; report ROC-AUC, PR-AUC, and reliability/Brier results; do not tune thresholds on holdout data.

Alternatives considered: Start with XGBoost; use random splits; optimize only recovery rate.

Why this approach: Logistic Regression is fast, inspectable, and adequate for validating the pipeline before model complexity.

Trade-offs: It may underfit nonlinear behavior, but an optional XGBoost comparison must not delay the core loop or weaken the model card.

Version/affected component: `MODEL_CARD.md`, recovery probability model.

## D-015 — Expected-net-value formula

Decision: Use a transparent action score rather than a black-box optimizer.

Date: 2026-08-24

Context: The PRD requires expected-net-value action selection and permits `DO_NOTHING`.

Chosen approach: `P(recovery | action, context) × amount_paise − action_cost_paise − incentive_cost_paise − fatigue_penalty_paise − policy/risk penalty`. Policy-infeasible actions cannot win; if every intervention is lower-value or blocked, select `DO_NOTHING`.

Alternatives considered: Maximize recovery probability alone; optimize contact volume; use an opaque optimizer.

Why this approach: It makes economic trade-offs and stopping behavior visible in the Decision Room and Arena.

Trade-offs: Results depend on illustrative costs and simulator probabilities, which must be disclosed and versioned.

Version/affected component: Decision engine, Arena metrics, simulator configuration.

## D-016 — Independent customer and environment state

Decision: Customer latent segments and environment/system state are separate variables.

Date: 2026-08-24

Context: Gateway and issuer/network degradation may affect any customer, regardless of customer behavior.

Chosen approach: Use four customer segments and independently sample `NORMAL`, `GATEWAY_DEGRADATION`, or `ISSUER_NETWORK_DEGRADATION` for each event. Environment state may change root-cause distribution and action deltas without replacing the customer segment.

Alternatives considered: Treat gateway degradation as a customer segment or make degradation mutually exclusive with behavioral segments.

Why this approach: It prevents the simulator from confusing system failures with customer traits and supports realistic coexistence.

Trade-offs: The simulator has more dimensions and requires explicit environment/action configuration.

Version/affected component: `simulator_v1.0.0` hidden-state and environment generator.

## D-017 — Strict seed separation

Decision: Training, validation, holdout, development Arena, and final Arena use disjoint seed ranges.

Date: 2026-08-24

Context: Final Arena results must not contain exact synthetic events used in model training or tuning.

Chosen approach: Training 100,000–199,999; validation 200,000–299,999; holdout 300,000–399,999; development/tuning Arena 400,000–499,999; final Arena 900,000–999,999. Event identity includes simulator version, split, seed, and event index.

Alternatives considered: Reuse one dataset across model and Arena; rely only on random event sampling.

Why this approach: Range separation is easy to audit and prevents accidental event reuse.

Trade-offs: More generated data and explicit split bookkeeping are required.

Version/affected component: Dataset generator, model pipeline, Arena runner.

## D-018 — Exact outcome horizon

Decision: A recovery outcome is evaluated in the half-open interval `[decision_timestamp, decision_timestamp + 7 days)`.

Date: 2026-08-24

Context: Arena comparisons need one precise outcome definition.

Chosen approach: The initial synthetic `decision_timestamp` equals the payment event timestamp. A recovered event has a successful payment inside the interval; an unrecovered event has none. A promise-to-pay is recorded as pending, pauses outreach, and schedules verification, but is not recovered revenue without a successful payment inside the interval.

Alternatives considered: Count promises as recovered; use a calendar-week boundary; allow outcomes after seven days.

Why this approach: It is deterministic and avoids overstating recovery from intent alone.

Trade-offs: Payments after the boundary are excluded from that decision's result even if they are eventually successful.

Version/affected component: `simulator_v1.0.0`, Arena metrics, voice outcome handling.

## D-019 — Contact-window scope

Decision: Contact-window enforcement applies only to outbound communication actions.

Date: 2026-08-24

Context: The PRD requires contact controls but does not intend to block non-contact financial or internal operations.

Chosen approach: Apply the configurable merchant/demo window to `SEND_MESSAGE`, `VOICE_RECOVERY`, and applicable human outreach. Do not block retries, internal status checks, or other non-contact actions.

Alternatives considered: Block every action outside the window; apply the window only to voice.

Why this approach: It matches the purpose of the control and preserves independent payment-retry behavior.

Trade-offs: The policy engine must classify actions by contact effect and document any future channel additions.

Version/affected component: Simulator defaults, policy engine, action adapters.

## D-020 — Immutable frozen results

Decision: Frozen simulator results are append-only by version and must never be silently overwritten.

Date: 2026-08-24

Context: Simulator changes can otherwise become hidden evaluation tuning.

Chosen approach: Store simulator version, source commit, configuration hash, seed range, and change reason with every result. A changed rule creates a new version and new report; prior reports remain available.

Alternatives considered: Regenerate existing results in place; update the current version after policy review.

Why this approach: It preserves an auditable evaluation history and prevents optimization against a moving ground truth.

Trade-offs: Reports and stored artifacts grow over time and require explicit version selection.

Version/affected component: Simulator release process, Arena reports, repository evaluation artifacts.

## D-021 — Observable-only baseline policy boundary

Decision: Gate 2 policies receive only `PaymentFailureEvent` and cannot access simulator truth.

Date: 2026-08-24

Context: Baselines must be comparable without latent-segment, environment-truth, future-outcome, or action-conditioned-probability leakage.

Chosen approach: Define one deterministic `choose_action(event)` interface. The Arena validates the selected action against the event's available actions and retains `HiddenState` and `SimulatorOutcome` inside the runner.

Alternatives considered: Pass a combined generated case to policies; expose simulator probabilities for diagnostic convenience.

Why this approach: It makes every policy face the same decision-time information and protects the validity of later model comparisons.

Trade-offs: Policies cannot use simulator-only explanations or counterfactual truth during Gate 2.

Version/affected component: Gate 2 policies, `backend/chimera_simulator/arena.py`.

## D-022 — Shared-batch Arena ordering and metrics

Decision: Generate one event batch per seed, share it across policies, select an action before resolving its outcome, and report paise-based recovery economics.

Date: 2026-08-24

Context: Comparative evaluation must be deterministic and must not let a policy observe realized outcomes before its choice.

Chosen approach: Use `Observable Event → Policy Action → Decision Record → Simulator Outcome → Metrics`. Store per-event JSON decision records, batch hashes, action counts, recovery, action/incentive/fatigue costs, intervention cost, gross value, net value, and contact-window diagnostics. Aggregate seed-level results with mean, min, max, and population standard deviation.

Alternatives considered: Generate separate batches per policy; compare recovery rate without costs; use significance testing in the baseline foundation.

Why this approach: Shared inputs and explicit accounting make the benchmark reproducible and auditable without adding database or service infrastructure.

Trade-offs: Seed-level standard deviation is descriptive and is not a confidence interval or significance claim.

Version/affected component: `backend/chimera_simulator/arena.py`, `docs/arena.md`, `data/simulator_v1/baseline_arena_dev.json`.

## D-023 — Gate 2 evaluation scope

Decision: Gate 2 benchmarks use only `arena_development` seeds 400000, 410000, 420000, 430000, and 440000; final Arena seeds remain untouched.

Date: 2026-08-24

Context: Development baselines may be inspected and used to validate the Arena before later model work.

Chosen approach: Run 1,000 events per approved development seed for each primary baseline and preserve the report with the simulator configuration hash.

Alternatives considered: Tune against final Arena seeds; use a single seed; introduce a random baseline as a primary benchmark.

Why this approach: It preserves the strict split boundary and provides enough repeated data to expose seed variation without adding unnecessary policy complexity.

Trade-offs: These results are development benchmarks only and must not be presented as final unseen-seed performance.

Version/affected component: Gate 2 Arena report and baseline policies.

## D-024 — Gate 3 observable feature schema

Decision: Train the recovery model on an explicit 44-feature schema built only from `PaymentFailureEvent` observables.

Date: 2026-08-24

Context: The model must estimate action-conditioned recovery without hidden-state or temporal leakage.

Chosen approach: Include scaled integer-paise amount, historical ratios, contact counts, time encodings, incident flag, observable payment/failure metadata, language/preferences, prior channel/response, contact-window eligibility, and candidate-action one-hot features. Exclude customer identifiers, synthetic PII, hidden segment/environment, simulator probabilities, outcomes, and future records. Reject any source timestamp after the decision timestamp.

Alternatives considered: Pass every event field to the model; expose simulator truth for stronger synthetic metrics; infer features from serialized truth records.

Why this approach: The feature contract is inspectable, reproducible, and enforceable at inference as well as training.

Trade-offs: Some available event fields are intentionally omitted, and the model cannot use latent variables that would be available only inside the simulator.

Version/affected component: `features_v1.0.0`, `backend/chimera_model/features.py`.

## D-025 — Gate 3 Logistic Regression and calibration

Decision: Use deterministic Logistic Regression as the first recovery model and Platt scaling on validation logits for calibration.

Date: 2026-08-24

Context: Gate 3 prioritizes interpretability, reproducibility, and probability calibration over maximum synthetic performance.

Chosen approach: Fit full-batch L2-regularized Logistic Regression on 35,000 training action rows using NumPy linear algebra. Fit Platt scaling once on 10,500 validation rows. Evaluate the untouched 10,500-row holdout and record per-action metrics.

Alternatives considered: XGBoost, neural models, repeated holdout tuning, isotonic calibration, and scikit-learn as a runtime dependency.

Why this approach: It keeps the model transparent and dependency-light while producing action-conditioned probabilities and a self-contained JSON artifact.

Trade-offs: The model may underfit nonlinear interactions; calibration improved validation Brier score only slightly from 0.208800 to 0.208767.

Version/affected component: `recovery_model_v1.0.0`, `MODEL_CARD.md`, `data/model_v1/`.

## D-026 — Gate 3 model experiment split manifest

Decision: Use fixed disjoint seed lists and 500 events per seed for the first model experiment.

Date: 2026-08-24

Context: Model fitting, calibration, and holdout evaluation must not consume Arena seeds or exact events across splits.

Chosen approach: Training seeds 100000, 110000, ..., 190000; validation seeds 200000, 210000, 220000; holdout seeds 300000, 310000, 320000. Generate seven action rows per event and persist the manifest and report with the simulator hash.

Alternatives considered: Use all seeds in each range; reuse the Gate 2 development Arena; randomly split action rows after generation.

Why this approach: The manifest is easy to reproduce and audit, and split validation is enforced before generation.

Trade-offs: The experiment is representative of the frozen synthetic distribution only; it is not evidence of production generalization.

Version/affected component: Gate 3 dataset pipeline, `data/model_v1/dataset_manifest.json`.

## D-027 — Gate 4 deterministic expected-net-value engine

Decision: CHIMERA selects the highest expected-net-value permissible action using the committed Gate 3 probability artifact.

Date: 2026-08-24

Context: The decision layer must remain deterministic, auditable, policy-constrained, and independent of LLM or persistence infrastructure.

Chosen approach: Evaluate all seven actions, block unavailable actions and outbound contact outside the configured window, calculate expected gross recovery with integer-paise `ROUND_HALF_UP`, subtract frozen action/incentive/fatigue costs, resolve one-paise near ties by friction, cost, then fixed action order, and emit a complete trace. Fatigue remains the frozen observable formula `fatigue_base[action] * (1 + contacts_last_7_days)`. The frozen ObservableContext contains no pending-promise field, so the engine does not infer promise-to-pay state.

Alternatives considered: Select the highest predicted probability; let an LLM choose; silently drop blocked actions; use floating-point INR comparison; tune the model after observing Arena action concentration.

Why this approach: It preserves financial determinism and exposes every economic and policy factor needed for audit.

Trade-offs: The Gate 4 development run selected `PAYMENT_LINK` for 100% of events. This is reported as a limitation of the current additive model/features, not corrected by tuning the frozen model or simulator.

Version/affected component: `chimera_engine_v1.0.0`, Gate 4 Arena report, `docs/engine.md`.

## D-028 — Gate 3.5 benchmark and model selection

Decision: Preserve `recovery_model_v1.0.0` and select
`recovery_model_v2_interaction_lr.0.0` as the Gate 3.5 probability-model
candidate.

Date: 2026-08-24

Context: Gate 4 showed `PAYMENT_LINK` selected for 100% of development events.
The model needed a controlled benchmark to determine whether the additive
action representation was underfitting observable action-context effects,
without tuning toward Arena performance.

Chosen approach: Benchmark the preserved 44-feature Logistic Regression, a
170-feature interaction Logistic Regression, and a deterministic NumPy
gradient booster over decision stumps. All use the same event-level training,
validation, and holdout seeds; all seven action rows remain grouped with their
source event. Candidates are fit on training, Platt-calibrated on validation,
then evaluated once on untouched holdout data. Arena seeds and Arena results
are excluded from selection.

Alternatives considered: Overwrite v1; tune features or costs until action
diversity increased; add a native CatBoost/LightGBM/XGBoost dependency; select
on development Arena revenue; use hidden simulator state.

Why this approach: The interaction representation directly tests the stated
modeling limitation while keeping the observable boundary and reproducibility
contract. The dependency-free tree benchmark provides a structured-model
comparison without adding an unpinned native runtime. The interaction model
had the best holdout probability quality: ROC-AUC `0.737706`, PR-AUC
`0.637621`, Brier `0.201287`, versus baseline Brier `0.205624` and tree Brier
`0.209414`.

Trade-offs: The interaction schema grows from 44 to 170 features and remains
synthetic-only. The stump booster is a transparent benchmark, not a mature
third-party gradient-boosting library. Selection does not prove Arena
improvement and no new Arena comparison was run. Gate 4 remains unchanged and
can consume the selected candidate only through the explicit compatibility
adapter.

Version/affected component: `features_v2.0.0_interaction`,
`recovery_model_v2_interaction_lr.0.0`,
`recovery_model_v3_gradient_boosting.0.0`, `data/model_benchmark_v1/`,
`backend/chimera_model/benchmark.py`.

## D-029 — Gate 4 re-evaluation with selected v2 model

Decision: Re-evaluate the existing Gate 4 engine with
`recovery_model_v2_interaction_lr.0.0` through the explicit
`Gate4ModelAdapter`, without changing the engine or Arena methodology.

Date: 2026-08-24

Context: Gate 3.5 selected the interaction model using validation and untouched
holdout probability quality. The downstream effect on CHIMERA must be observed
on the fixed development Arena.

Chosen approach: Load the versioned v2 artifact, validate simulator version,
configuration hash, and interaction feature schema, then run the existing
engine against the five approved development seeds with 1,000 events each and
the three existing baselines. Separately repeat the run, reverse policy order,
and remove the other policies to verify deterministic CHIMERA decisions.

Alternatives considered: Modify Gate 4 compatibility logic; retrain or
calibrate the model; tune costs, fatigue, constraints, tie-breaking, or the
simulator; select the model using Arena outcomes.

Why this approach: It isolates the effect of replacing the probability model
and preserves the financial decision contract. The re-evaluation selected all
seven actions, with `PAYMENT_LINK` at 51.98%, and the selected action differed
from raw highest probability on 22.50% of events.

Trade-offs: CHIMERA's synthetic development recovery and net value exceeded
`SIMPLE_RULE_BASED` in this fixed run, but no significance test or real-world
claim is made. Seed-level recovery standard deviation increased from 0.5352%
to 0.9867%. The report remains downstream evaluation evidence only.

Version/affected component: `gate4_reevaluation_v2.0.0`,
`data/model_benchmark_v1/gate4_reevaluation_v2_report.json`,
`backend/scripts/run_gate4_reevaluation_v2.py`.

## D-030 — Explanation authority and append-only history

Decision: Gate 6 explanations are optional, validated annotations of stored
deterministic decisions, never decision inputs or action authority.

Date: 2026-08-24

Context: Operators need concise explanations, but an LLM must not change
probabilities, costs, scores, constraints, selected actions, or execution.

Chosen approach: Build an allowlisted context from persisted
`RecoveryCase`, `Decision`, and `DecisionCandidate` records. Validate strict
structured output, require the recommendation to equal the stored selected
action, and persist one immutable explanation row per explicit request.
Repeated requests remain in append-only history; latest lookup orders by
`generated_at DESC, id DESC`.

Alternatives considered: Let the LLM recalculate scores; overwrite the latest
explanation; persist raw provider responses and errors.

Why this approach: It preserves deterministic financial behavior and makes
every explanation reproducible and auditable without duplicating Gate 4 logic.

Trade-offs: Explanations may fall back to templates, and qualitative text is
less expressive because unvalidated numeric and monetary claims are rejected.

Version/affected component: `chimera_explanation_v1.0.0`,
`explanation_v1.0.0`, `explanations` table, intelligence service.

## D-031 — OpenAI-compatible provider boundary

Decision: Use an optional OpenAI-compatible HTTP provider without a vendor SDK.

Date: 2026-08-24

Context: Gate 6 requires at least one optional provider while keeping the
application runnable and testable without a paid API or external key.

Chosen approach: Configure provider name, base URL, model, API key, and
timeout through server-side environment variables. Use mocked providers in
tests and deterministic fallback when the provider is absent or fails.

Alternatives considered: Require an OpenAI SDK; call an LLM during every
decision; expose provider credentials to the frontend.

Why this approach: It keeps the dependency surface small and supports
OpenAI-compatible deployments while preserving the provider abstraction.

Trade-offs: Provider response compatibility remains an operational concern;
the adapter supports the chat-completions JSON response shape only.

Version/affected component: `backend/chimera_intelligence/provider.py`,
`.env.example`.

## D-032 — Gate 7 operator frontend boundary

Decision: Gate 7 is a presentation and operator workflow layer over the
persisted Gate 5 and Gate 6 backend contracts.

Date: 2026-08-25

Context: Operators need to inspect cases, understand stored deterministic
decisions, review optional explanations, and execute only eligible actions
without moving financial logic into the browser.

Chosen approach: Build a Next.js/TypeScript frontend with Command Center,
Recovery Cases, and Decision Room routes. Use a centralized typed API client;
render actual case, decision, candidate, explanation, and execution response
fields; and call the existing backend endpoints for decision generation,
explanation generation, and execution.

Alternatives considered: Duplicate expected-value logic in the frontend;
recompute candidate rankings client-side; call providers directly from the
browser; add a second backend.

Why this approach: The backend remains authoritative and the operator can
audit the exact stored trace that governs execution. The browser remains safe
to deploy without provider credentials and cannot alter deterministic behavior.

Trade-offs: Aggregate dashboard metrics are limited to data returned by the
current list API. Historical context, recovery reconciliation, authentication,
and richer analytics remain backend/product work for later gates.

Version/affected component: `frontend/`, `docs/frontend.md`,
`docs/architecture.md`. No simulator, model, engine, or Gate 0–6 authority
boundary changed.

## D-033 — Gate 7 recovery control-room redesign

Decision: Reframe the frontend around the recovery lifecycle and observable operational work instead of generic dashboard metrics.

Date: 2026-08-25

Context: The first frontend pass presented cases and stored decisions, but did not make the agent's detect → diagnose → decide → intervene → recover workflow immediately legible.

Chosen approach: Use a dark incident-response control room with meaningful revenue-at-risk metrics, active-problem flow, observed failure/root-cause views, stored activity milestones, ranked candidate action cards, explicit policy constraints, intervention status, recovery outcome truth states, and dedicated intelligence/audit routes.

Alternatives considered: Retain the existing admin-style table dashboard; add fabricated charts, trends, or recovery events; move decision calculations into the browser.

Why this approach: It matches the operator's actual task while preserving the backend as the sole authority for probabilities, economics, policies, execution, and outcomes. Missing backend facts remain honest empty or pending states.

Trade-offs: Friendly REC-### IDs, true historical trends, customer names, granular audit events, and recovered amounts are not invented because the current API does not provide them. The UI uses external event IDs, stored timestamps, case status, and stored amounts instead.

Version/affected component: `frontend/`, `DESIGN.md`, `docs/frontend.md`. Gate 0–6 behavior and API contracts unchanged.

## D-034 — Gate 7 provider-independent intervention lifecycle

Decision: Model intervention orchestration as a separate append-only operational
layer that consumes stored decisions and does not recompute or reinterpret them.

Date: 2026-08-26

Context: Operators need a durable lifecycle from a persisted deterministic
decision through queueing, execution acceptance, and a later recovery outcome.
Gate 7 must be testable without Razorpay, messaging, or telephony credentials.

Chosen approach: Add `Intervention`, append-only `InterventionExecution`,
`InterventionEvent`, and `InterventionOutcome` records. Use an explicit state
machine, deterministic SHA-256 idempotency keys, strict approved execution
context, deterministic local executors, and monotonic per-intervention audit
sequence numbers. Copy `Decision.selected_action` exactly; create a terminal
`COMPLETED` record for `DO_NOTHING`.

Alternatives considered: Reuse Gate 5 `ActionExecution`; let the intervention
layer rerun the decision engine; call providers directly; treat execution
acceptance as recovery; overwrite one mutable status/history row.

Why this approach: It keeps decision authority, operational authority, and
provider authority separate, preserves replayable history, and allows Gate 8
providers to attach without changing deterministic decision behavior.

Trade-offs: Gate 7 local executors cannot confirm real payment recovery, contact
eligibility is explicitly unavailable in the persisted Gate 5 case contract,
and cancellation/retry policy surface remains intentionally small until the
provider integration gate.

Version/affected component: `backend/app/interventions/`, `interventions`,
`intervention_executions`, `intervention_events`, `intervention_outcomes`,
`docs/interventions.md`, migration `0003_gate7_interventions`.

## D-035 — Gate 8 controlled voice execution boundary

Decision: Add voice as a constrained execution adapter attached only to a
stored `VOICE_RECOVERY` intervention; conversation intent must never become a
new CHIMERA action or payment-success signal.

Date: 2026-08-26

Context: The demo needs a realistic voice recovery interaction while the
deterministic decision engine, policy checks, and payment outcome boundary
remain authoritative.

Chosen approach: Persist `VoiceCall`, append-only `VoiceTurn`, and append-only
`VoiceEvent` records. Use a validated voice-call state machine, strict
allowlisted `VoiceContext`, deterministic local scenarios, and a provider-
neutral live HTTP adapter configured through `VOICE_*` environment variables.
Payment-link requests create deterministic demo links only; positive speech
records a pending conversational result and does not mark recovery.

Alternatives considered: Let an LLM choose a follow-up action; treat customer
agreement as recovered; store raw provider payloads; hardcode a telephony
vendor into Gate 7; require paid credentials for the demo.

Why this approach: It provides a judge-ready local flow, preserves decision and
policy authority, creates a replayable audit trail, and leaves live provider
translation replaceable without changing the intervention lifecycle.

Trade-offs: Live calls require a configured provider endpoint, destination
number, agent identifier, and credentials; speech recognition is represented by
validated intent extraction/provider events rather than a vendor-specific STT
implementation; Razorpay/payment confirmation remains a later boundary.

Version/affected component: `backend/chimera_voice/`, `voice_calls`,
`voice_turns`, `voice_events`, migration `0004_gate8_voice_agent`,
`docs/voice_agent.md`.

## D-036 — Gate 9 provider-authoritative payment boundary

Decision: Add a provider-neutral payment-link boundary with deterministic local
demo behavior and an isolated Razorpay adapter. Only a validated provider
success event may mark an intervention recovered.

Date: 2026-08-26

Context: Gate 8 can validate a customer request for a payment link, but it must
not create payment instruments or claim recovery. Real payment confirmation
needs durable, replayable provider references and event history.

Chosen approach: `PaymentService` reads the stored intervention, decision, and
case; it creates one idempotent link through `PaymentProvider`, persists
sanitized request/result hashes, and appends `PaymentEvent` rows. Webhooks are
verified against the raw body, provider event IDs are idempotent, amounts and
currency are checked in integer paise/INR, and terminal PAID state is monotonic.
Voice may call the service only after validated `SEND_PAYMENT_LINK` intent.

Alternatives considered: Let voice or frontend create links; treat link
creation, customer intent, or a redirect as recovery; persist raw provider
payloads; use a Razorpay SDK directly throughout the app; use mutable-only
payment status.

Why this approach: It preserves Gate 4/7/8 authority boundaries, supports a
credential-free local demo, and leaves live Razorpay transport replaceable.

Trade-offs: Local provider state is process-local and is for demonstration;
Razorpay reconciliation requires configured test credentials; payment-link
creation is intentionally limited to the selected intervention action.

Version/affected component: `backend/chimera_payments/`, payment tables,
migration `0005_gate9_payments`, payment routes, Gate 8 payment-link handoff,
`docs/payments.md`.

## D-037 — Gate 10 provider-neutral recovery orchestration

Decision: Route persisted interventions to messaging, retry, scheduling, or
escalation services without introducing a second decision layer.

Date: 2026-08-26

Context: Gates 7–9 established lifecycle, voice, and payment boundaries, but
`SEND_MESSAGE`, retry actions, and escalation still had no complete workflow.

Chosen approach: Add `RecoveryOrchestrator` keyed only by
`Intervention.action`; add deterministic local messaging/templates, a Twilio
boundary, deterministic retry scheduling, a provider-neutral retry interface,
and an append-only escalation event stream. Reuse active Gate 9 payment links
and request a link through Gate 9 only for a SEND_MESSAGE workflow when none is
active. Persist operation records and safe hashes; provider acceptance never
means payment recovery.

Alternatives considered: Recompute decisions during execution, let providers
choose follow-up actions, add a queue broker, treat message delivery or retry
acceptance as recovery, or make escalation a no-op audit line.

Why this approach: It makes the selected intervention observable and
executable while preserving deterministic decision authority and the existing
payment/voice boundaries.

Trade-offs: Local delivery and retry providers are synthetic; Twilio requires a
configured destination number for live operation; retry schedules use a simple
24-hour deterministic policy until a later gate defines richer scheduling.

Version/affected component: `backend/chimera_messaging/`,
`backend/chimera_retry/`, `backend/chimera_orchestration/`, migration
`0006_gate10_orchestration`, API routes, and `docs/orchestration.md`.

## D-038 — Gate 11 provider modes and persisted journey projection

Decision: Add explicit `LOCAL`, `MOCK`, `TEST`, and `LIVE` provider modes and
compose the existing decision/intervention/orchestration services behind a
demo endpoint and a persisted journey projection.

Date: 2026-08-26

Context: The buildathon demo must distinguish deterministic local execution
from sandbox/live provider calls and show one complete recovery story without
changing decision authority or the frozen simulator/model layers.

Chosen approach: Persist `provider_mode` on each external-operation record and
event. `POST /api/v1/demo/recovery` accepts the existing observable case schema,
calls the existing services in order, and returns inspectable IDs.
`RecoveryJourneyService` reads stored case, decision, candidates, intervention,
provider, outcome, explanation, and audit rows; it sorts the append-only event
projection by timestamp, event type, and ID.

Alternatives considered: Add a queue/broker, create a second decision path,
allow a client-supplied action, or infer historical state by rerunning the
engine.

Why this approach: It keeps the MVP local-first and auditable while allowing
Razorpay/Twilio-compatible integrations to be enabled explicitly through
server-side configuration.

Trade-offs: A provider mode is an execution label, not proof that credentials
were valid or a real transaction occurred. The local demo remains synthetic;
live voice is unavailable until a safe provider endpoint and credentials are
configured. Journey payloads intentionally expose sanitized provider records,
not raw secrets or request bodies.

Version/affected component: `backend/provider_modes.py`, provider services,
`RecoveryJourneyService`, demo/journey routes, migration
`0007_gate11_provider_modes`.

## D-039 — Gate 13 read-only recovery intelligence projection

Decision: Build case-level recovery intelligence as a deterministic,
observable-only projection over persisted journey records.

Date: 2026-08-26

Context: Operators need one coherent explanation of detection, likely root
cause, stored decision, intervention, outcome, and learning without weakening
the Gate 4 decision authority or exposing simulator truth.

Chosen approach: Add `RecoveryIntelligenceService` and explicit Pydantic
schemas behind `GET /api/v1/recovery-cases/{case_id}/intelligence`. Reuse the
persisted `RecoveryJourneyService` projection; classify root causes from
observable failure reason/incident/contact signals; copy decision economics
and trace flags; derive outcome status only from persisted lifecycle records;
and produce descriptive deterministic insights. Use the documented display
severity thresholds of 100,000 and 25,000 paise. Label local/mock/test voice
records `Demo Voice Agent` and require a persisted live provider reference for
live wording.

Alternatives considered: Re-run the model or decision engine on read; add a
second decision path; call the LLM by default; expose hidden simulator state;
persist a new intelligence table.

Why this approach: It is side-effect-free, replayable, honest about causal
uncertainty, and gives the frontend one complete narrative without a schema or
migration dependency.

Trade-offs: Root-cause categories are operational interpretations, not causal
proof. Cases created before provider/journey records may show partial
intervention or outcome detail. Severity thresholds are display assumptions,
not merchant risk policy.

Version/affected component: `backend/chimera_intelligence/`, intelligence
endpoint, Decision Room, `docs/recovery_intelligence.md`.

## D-040 — Gate 16 explicit provider readiness and live safety

Decision: Add a provider-health boundary that reports configured provider
capabilities and persists append-only verification attempts without granting
provider execution or decision authority.

Date: 2026-08-27

Context: Provider adapters exist for local demos and optional external
execution, but credentials or mock tests must not be presented as real-world
verification.

Chosen approach: Reuse existing provider objects and add only
side-effect-free connectivity probes. Classify `LOCAL`/`MOCK` as
`MOCK_VERIFIED`, `TEST` and `SANDBOX` only after a successful explicit probe,
and `LIVE` only after a successful probe with
`CHIMERA_ALLOW_LIVE_EXECUTION=true`. Persist controlled results and hashes in
`provider_verifications`; never persist secrets or raw provider errors.

Alternatives considered: Treat credentials as verified, invoke a customer
action during readiness checks, add a provider SDK, or create a second
execution path.

Why this approach: It gives operators honest integration posture while
preserving the intervention lifecycle and deterministic decision authority.

Trade-offs: The voice adapter remains provider-neutral and requires a
vendor-compatible `/health` endpoint. No external provider can be claimed
verified until credentials are supplied and the appropriate probe is
deliberately run.

Version/affected component: `backend/chimera_provider_health/`, provider
readiness APIs, `provider_verifications`, migration `0010_gate16_provider_health`,
and the Command Center provider posture panel.
