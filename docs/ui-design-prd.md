# CHIMERA UI Design PRD

## Document status

- Status: Design baseline for implementation
- Product: CHIMERA Revenue Recovery Intelligence
- Surface: Operator-facing web application
- Audience: Recovery operations analysts first; risk/operations managers and buildathon reviewers second
- Implementation status: Documentation only; no UI implementation is defined by this document

## 1. Product definition

CHIMERA is an operator-guided autonomous recovery agent. It receives observable payment-failure context, produces a stored deterministic decision, routes an approved intervention through a provider boundary, waits for a verified outcome, and records an auditable recovery journey.

The product is not organized around backend packages or LLM features. It is organized around the operator's questions:

1. What failed?
2. What should happen next?
3. Is CHIMERA allowed to do it?
4. Did the provider actually do it?
5. Was recovery confirmed?

The primary lifecycle is:

```text
Detect → Diagnose → Decide → Intervene → Recover → Learn
```

The deterministic recovery engine and policy layer are authoritative. Optional generative AI may support explanations and voice interactions, but it must never be presented as the authority for financial action, policy enforcement, provider acceptance, or successful recovery.

## 2. Product goals

### Primary goals

- Let an operator understand an active payment-failure case quickly.
- Make the next safe action obvious.
- Show why an action was selected without recreating backend logic in the browser.
- Prove what happened after an intervention through provider receipts, webhooks, outcomes, and audit events.
- Make synthetic, local, mock, test, sandbox, and live modes unmistakable.
- Give buildathon reviewers a reliable path from scenario setup to verifiable end-to-end evidence.

### Secondary goals

- Make stored outcomes useful for observational analysis.
- Make provider readiness and system health inspectable without exposing secrets.
- Preserve a calm, trustworthy, information-dense financial-operations tone.

### Non-goals

- Building an LLM-first chatbot interface.
- Allowing the frontend to select, rank, or modify recovery actions.
- Showing hidden simulator state, latent variables, future outcomes, or credentials.
- Creating a generic analytics warehouse on the Command Center.
- Creating separate top-level products for payments, messaging, voice, retries, or escalation.
- Claiming causal superiority or real-world performance from synthetic observed data.
- Adding ownership, assignment, SLA, or bulk-execution workflows before the backend supports them.

## 3. Locked information architecture

```text
Command Center

Recovery Operations
  ├─ Case Queue
  ├─ Action Queue
  ├─ Escalations
  └─ Scheduled Retries

Intelligence
  ├─ Failure Patterns
  ├─ Recovery Outcomes
  └─ Outcome Learning

System
  ├─ System Health
  ├─ Decision Engine
  └─ Audit Trail

Providers
  └─ Provider Readiness

Evaluation Lab
  ├─ Demo Scenarios
  ├─ Recovery Arena
  └─ Methodology & Guardrails
```

### Navigation rules

- Command Center is one overview page with no child pages.
- Recovery Operations owns active work and operator actions.
- Decision Room is a contextual case-detail destination, not a primary sidebar item.
- Payment, messaging, voice, retry, and escalation records appear inside intervention and provider contexts.
- Intelligence is read-only analysis. It links back to cases but does not execute actions.
- System describes CHIMERA's internal health and decision authority.
- Providers describes external execution dependencies and their readiness.
- Evaluation Lab is the safe, reproducible demonstration and comparison space.
- Provider-specific detail pages open from Provider Readiness instead of becoming permanent sidebar links.

## 4. Global shell

### Sidebar

The sidebar is a persistent desktop operations rail with collapsible groups. It should show no more than the six primary destinations above.

The active item must remain visible through:

- clear label contrast
- a narrow active rule or pip
- a restrained background treatment
- an optional count badge only for actionable queues

Counts are allowed on `Action Queue`, `Escalations`, and `Scheduled Retries`. Do not add counts to `System`, `Providers`, or analytical pages unless the count represents a real exception.

### Top bar

The top bar contains:

- breadcrumb: `CHIMERA / current workspace / current page`
- global case search by case ID, payment ID, external event ID, or customer ID
- environment badge: `Demo`, `Test`, or `Live`
- provider execution mode when relevant: `LOCAL`, `MOCK`, `TEST`, `SANDBOX`, or `LIVE`
- compact system-status indicator

The top bar must not imply that CHIMERA is an LLM product. The preferred transparency pattern is:

```text
CHIMERA Recovery Agent
Decision authority: deterministic recovery engine
AI assistance: optional; explanations and voice only
```

### Environment and trust banner

Every page that can display provider activity must visibly distinguish:

```text
Environment: Demo
Data: Synthetic
Provider mode: Local
```

Provider mode is not the same as recovery status. `TEST_VERIFIED` does not mean `RECOVERED`.

### Global component states

Every data-backed surface supports:

- loading
- empty
- unavailable backend
- not found
- stale data or refresh required
- permission or action-not-allowed
- provider unavailable
- invalid transition
- successful mutation

Error messages must use safe, human-readable categories and must never expose stack traces, secrets, raw signatures, or unsanitized provider responses.

## 5. Command Center

### Job

Command Center is the operational pulse. It should be understandable in ten seconds and should not duplicate the deeper analytical workspaces.

It answers:

1. How much revenue is currently exposed?
2. What needs attention now?
3. Is recovery progressing?
4. Is anything in the system or provider layer blocked?

### Page structure

```text
Command Center
  ├─ Summary metrics
  ├─ Needs Attention Now
  ├─ Recovery Pipeline
  ├─ System Posture
  ├─ Recent Recovery Activity
  └─ Failure Pulse
```

### Summary metrics

Show four primary metrics:

- Revenue at risk: unresolved stored case value
- Recovered revenue: stored recovered value
- Active interventions: interventions in non-terminal operational states
- Human review needed: pending escalation work

Each metric links to its source workspace. Avoid vanity metrics such as API calls, model confidence, total records, or provider capability counts.

### Needs Attention Now

This is the largest module on the page. Show no more than five to seven high-signal rows.

Supported examples:

- decision created but intervention not executed
- intervention awaiting outcome
- escalation awaiting acknowledgement
- retry eligible or due
- payment link pending
- provider operation failed
- contact window or policy boundary requiring review

Every row must expose:

```text
What happened?  Why does it matter?  What is the next action?
```

Primary action opens the relevant queue or Decision Room.

### Recovery Pipeline

Use persisted operational states rather than pretending that diagnosis is a separate stored status:

```text
New → Decision ready → Intervention running → Outcome pending → Recovered / Unrecovered
```

The pipeline is a quick distribution view, not a funnel-performance analysis. The full funnel belongs in Intelligence.

### System Posture

Show compact health indicators for:

- decision engine
- API/database compatibility
- Razorpay
- messaging
- voice
- retry
- escalation

Healthy items recede visually. Exceptions link to System or Providers.

### Recent Activity

Show a short chronological list of persisted events:

- decision created
- intervention queued
- provider action accepted
- payment link created
- voice interaction completed
- escalation acknowledged
- recovery confirmed

Every event opens the case journey or audit context.

### Failure Pulse

Show only a compact summary of the current pressure:

- top failure reasons
- affected cases
- value at risk by reason
- active incident signal

The complete pattern analysis belongs in `Intelligence → Failure Patterns`.

### Command Center anti-goals

- no full learning reports
- no full audit table
- no detailed candidate economics
- no full provider configuration cards
- no Arena comparison table
- no voice transcript
- no large demo control panel

## 6. Recovery Operations

### Job

Recovery Operations is the main operator workbench. It answers:

> Which recovery cases need attention, what is the next safe action, and what evidence is available?

### Workspace navigation

```text
Recovery Operations
  ├─ Case Queue
  ├─ Action Queue
  ├─ Escalations
  └─ Scheduled Retries
```

### Shared page structure

```text
Page header
Queue tabs
Queue summary strip
Search and filters
Dense operational table
Empty/error state
```

### Queue summary strip

Use concise actionable counts:

```text
Needs decision · Ready to act · Awaiting outcome · Human review
```

Each count deep-links to a filtered or purpose-specific queue.

### Case Queue

Purpose: understand what failed and identify cases that need work.

Filters:

- search
- recovery status
- failure reason
- payment method
- incident signal
- selected action
- provider mode

Primary columns:

```text
Status
Amount at risk
Failure reason
Observable diagnosis
Selected action
Intervention state
Last activity
Next action
```

The user should not need to interpret raw backend status codes before understanding the case.

### Action Queue

Purpose: act on persisted interventions, not merely cases whose status happens to be `DECIDED`.

The conceptual lifecycle is:

```text
CREATED → QUEUED → READY → EXECUTING → AWAITING_OUTCOME → terminal
```

Primary columns:

```text
Priority
Case context
Action
Intervention status
Created / eligible time
Provider mode
Next action
```

Financial and outbound actions require explicit operator intent and backend eligibility. No bulk execution of payment or outreach actions.

### Escalations

Purpose: handle cases requiring human judgment.

Each row shows:

- priority
- escalation reason
- case amount and failure context
- current status
- created time
- next human action

Primary actions are `Acknowledge` and `Resolve`, subject to backend state transitions.

### Scheduled Retries

Purpose: show what is scheduled for later and whether it is currently eligible.

Each row shows:

- case and action
- scheduled time
- eligibility status
- execution status
- provider mode
- next allowed action

Do not make scheduled retries look like failed actions. They are future work until eligibility is reached.

### Shared row behavior

Every active row has one clear next-action label:

- Review decision
- Execute approved intervention
- Monitor outcome
- Acknowledge escalation
- Resolve escalation
- Retry now
- Wait until eligible
- Investigate provider failure

The default row click opens the full Decision Room. A lightweight preview can be added later, but it must not replace the full detail experience.

## 7. Decision Room

### Job

Decision Room is the case-level workspace. It presents one coherent recovery story rather than a set of backend objects.

### Page structure

```text
Case header
  ├─ amount at risk
  ├─ failure reason
  ├─ current recovery state
  ├─ selected action
  └─ environment/provider mode

Recovery story
  ├─ Problem
  ├─ Diagnosis
  ├─ Decision
  ├─ Intervention
  ├─ Execution Proof
  └─ Outcome

Supporting evidence
  ├─ Candidate actions
  ├─ Explanation history
  └─ Audit journey
```

### Case header

The header must make the case actionable at a glance:

```text
Case status
Amount at risk
Payment method
Failure reason
Incident signal
Selected action
Provider mode
Next action
```

Customer and payment identifiers are shown as stable references, not as fabricated names or friendly IDs that do not exist in the API.

### Diagnosis

Show observable evidence:

- primary cause category
- confidence level
- evidence fields
- contributing factors
- alternatives
- uncertainty statement

Do not imply hidden customer segments, latent causes, or future certainty.

### Stored Decision

Show the backend-stored decision as authoritative:

- selected action
- predicted probability
- expected gross recovery
- expected net value
- model version
- feature schema version
- engine version
- simulator/configuration version where available

Candidate actions remain visible, including blocked actions and stored blocked reasons.

### AI transparency

If an explanation exists, show:

```text
Explanation source: LLM / deterministic fallback
Provider: provider name or local fallback
Model: model name when available
Generated at: timestamp
Fallback reason: when applicable
```

The explanation is supporting context and append-only history. It cannot alter the decision.

### Intervention

Show lifecycle state and operator controls:

```text
Created → Queued → Ready → Executing → Awaiting outcome → Terminal
```

The selected action must be copied from the stored Decision. The UI must never offer a control to substitute another action.

### Execution Proof

This is the evidence component for demos and real operations.

For payment links:

- provider name
- provider mode
- link status
- amount and currency
- provider reference
- safe link action
- webhook state
- reconciliation state

For voice:

- provider name
- provider mode
- call status
- provider call reference
- transcript turns
- detected intent
- resulting operational action

For messaging, retry, and escalation:

- provider or workflow name
- acceptance/delivery/schedule status
- reference
- relevant events
- outcome boundary

Provider acceptance is never displayed as recovery. Recovery requires the persisted outcome authority.

### Outcome

Show:

- outcome state
- recovered amount when present
- timestamp
- time to outcome when available
- recovery path
- clear pending/unresolved language

### Audit Journey

Use a chronological, append-only timeline with:

- event type
- source
- timestamp
- provider mode
- linked entity
- safe payload summary

## 8. Intelligence

### Job

Intelligence is a read-only evidence workspace. It explains patterns and stored outcomes without selecting actions or making causal claims.

### Structure

```text
Intelligence
  ├─ Failure Patterns
  ├─ Recovery Outcomes
  └─ Outcome Learning
```

No separate permanent sidebar links for calibration, drift, funnel, providers, insights, or recommendations.

### Evidence header

Every page displays:

```text
Data: synthetic stored records
Sample size: N cases
Provider modes: ...
Last updated: ...
Interpretation: observed, not causal
```

### Failure Patterns

Purpose: understand what is failing and where value is exposed.

Components:

- revenue exposed
- affected cases
- incident signals
- most common failure reason
- failure distribution
- value at risk by reason
- observable root-cause evidence
- cases by pattern

Clicking a pattern opens a filtered Case Queue.

### Recovery Outcomes

Purpose: understand what happened after interventions.

Components:

- recovered revenue
- observed recovery rate
- unresolved value
- completed cases
- outcome by intervention
- action comparison table
- recovery funnel
- recent outcomes

Recommended table columns:

```text
Action | Selected | Completed | Recovery rate | Gross value | Net value | Reliability
```

### Outcome Learning

Purpose: inspect observational learning from persisted recovery journeys.

Use page-level tabs:

```text
Overview | Actions | Failure groups | Funnel | Providers | Calibration | Drift | Insights
```

Modules:

- overall case and recovery summary
- action performance
- failure-group performance
- recovery funnel
- provider performance by mode
- predicted versus observed calibration
- baseline versus current drift
- evidence-backed insights
- human-reviewed recommendations

Each insight card includes:

```text
Finding
Evidence
Sample size
Reliability
Limitation
```

Each recommendation card includes:

```text
Recommendation
Supporting evidence
Review requirement
```

The page must clearly state that it does not retrain the model or change stored decisions.

## 9. System

### Job

System is CHIMERA's internal control plane. It answers:

> Is CHIMERA itself healthy, explainable, and auditable?

### Structure

```text
System
  ├─ System Health
  ├─ Decision Engine
  └─ Audit Trail
```

### System Health

Show:

- overall system status
- API status
- database status
- model compatibility
- environment
- current versions
- recent internal errors or degraded components

Show the internal pipeline:

```text
Event → Context → Model → Scoring → Policy → Intervention → Outcome
```

Show safety posture:

- backend is decision authority
- financial actions are policy validated
- webhook/outcome boundary determines recovery
- optional AI is non-authoritative
- live execution requires explicit enablement

### Decision Engine

Show read-only decision provenance:

- model version
- feature schema version
- engine version
- simulator version
- policy name/version
- active constraints
- fatigue rules
- tie-breaking behavior

Do not expose secrets or unsupported internal model details. Per-case traces belong in Decision Room.

### Audit Trail

Provide a global evidence table with:

```text
Timestamp | Event | Source | Case | Decision | Intervention | Provider mode | Status
```

Filters:

- time window when supported
- event type
- source
- provider mode
- status
- case/reference search

The audit surface is read-only and append-only.

## 10. Providers

### Job

Providers is the external execution control plane. It answers:

> Can each external dependency safely perform its assigned role?

### Structure

```text
Providers
  └─ Provider Readiness
```

Provider detail pages open from the overview and are not permanent sidebar links.

### Provider Readiness

Show a readiness matrix:

```text
Provider | Type | Mode | Readiness | Capabilities | Last verified | Latency
```

Providers include:

- Razorpay
- messaging
- voice
- retry
- escalation

Status vocabulary:

- Ready
- Needs attention
- Not configured
- Verification failed
- Mock verified
- Test verified
- Sandbox verified
- Live verified

### Provider detail

Each provider detail view includes:

- provider name and type
- current provider mode
- readiness status
- capabilities
- limitations
- last verification result
- verification history
- safe verification control
- explicitly confirmed test control when permitted
- recent sanitized provider events

Never display:

- API keys
- secrets
- authorization headers
- webhook signatures
- raw provider responses

Readiness must never be confused with recovery outcome. A provider can be ready while a payment remains pending.

## 11. Evaluation Lab

### Job

Evaluation Lab is the buildathon-facing proof workspace. It runs controlled, reproducible scenarios using the same decision, intervention, provider, and audit systems as the main product.

### Structure

```text
Evaluation Lab
  ├─ Demo Scenarios
  ├─ Recovery Arena
  └─ Methodology & Guardrails
```

### Demo Scenarios

Default page. Its first question is:

> What do you want to demonstrate?

Scenario cards:

- Payment Recovery
- Voice-Assisted Recovery
- Technical Retry
- Human Escalation

Each card shows:

- failure setup
- workflow being demonstrated
- evidence expected
- provider mode
- synthetic/test warning

The run experience is:

```text
Scenario setup
→ Failure received
→ Decision created
→ Intervention authorized
→ Provider action
→ Outcome
→ Audit journey
```

The run monitor must use actual persisted event timestamps and references. Avoid fake progress animation that implies an event before the backend records it.

### Demo mode transparency

Always show:

```text
Environment: Demo
Data: Synthetic
Provider mode: Local / Mock / Test
```

If a local voice scenario creates a deterministic transcript but no external phone call, label it `Demo Voice Agent` and never imply that a customer was called.

If Razorpay test mode is connected, show `Razorpay TEST`, the provider reference, and the actual test payment link. If it is local, show `Local demo provider` and `Synthetic payment link`.

### Recovery Arena

Purpose: compare strategies against the same synthetic event batch.

Configuration:

- development seeds
- events per seed
- simulator version
- configuration hash

Results:

- recovered revenue
- net value
- interventions
- policy violations
- recovery rate

Integrity panel:

- same event batch across strategies
- synthetic data
- reproducible run
- simulator/configuration versions

Include a clear interpretation boundary: comparative synthetic evaluation is not a real-world performance claim.

### Methodology & Guardrails

Explain:

- what CHIMERA observes
- what the predictive model estimates
- what the deterministic policy engine controls
- what the intervention orchestrator controls
- what provider webhooks prove
- where optional AI can participate
- what the system explicitly does not claim

This is the primary reviewer-facing trust page.

## 12. Reusable component inventory

### Shell components

- `AppShell`
- `Sidebar`
- `SidebarSection`
- `TopBar`
- `Breadcrumbs`
- `EnvironmentBadge`
- `ProviderModeBadge`
- `SystemStatusIndicator`
- `GlobalSearch`

### Navigation and page components

- `PageHeader`
- `SectionHeader`
- `QueueTabs`
- `FilterBar`
- `RefreshControl`
- `DeepLinkAction`

### Data and status components

- `MetricCard`
- `StatusBadge`
- `SeverityBadge`
- `ModeBadge`
- `ReadinessBadge`
- `EvidenceHeader`
- `DataBoundaryCallout`
- `SampleSizeLabel`
- `EmptyState`
- `LoadingState`
- `ErrorState`
- `StaleDataNotice`

### Operations components

- `QueueSummaryStrip`
- `CaseTable`
- `CaseRow`
- `NextActionButton`
- `AttentionIndicator`
- `InterventionStatusStepper`
- `EscalationRow`
- `ScheduledRetryRow`
- `DecisionRoomHeader`
- `CandidateActionTable`
- `ConstraintList`
- `ExecutionProof`
- `ProviderReceipt`
- `OutcomeSummary`
- `AuditTimeline`

### Intelligence components

- `FailurePatternList`
- `FailureDistribution`
- `OutcomeComparisonTable`
- `RecoveryFunnel`
- `CalibrationPanel`
- `DriftPanel`
- `InsightCard`
- `RecommendationCard`

### System and provider components

- `SystemHealthGrid`
- `DecisionProvenance`
- `SafetyPosturePanel`
- `AuditEventTable`
- `ProviderReadinessMatrix`
- `ProviderDetailHeader`
- `CapabilityList`
- `VerificationHistory`
- `SafeVerificationControl`

### Evaluation components

- `ModeBanner`
- `ScenarioCard`
- `ScenarioSetup`
- `DemoRunMonitor`
- `ProviderReceipt`
- `RunSummary`
- `ArenaConfiguration`
- `ArenaComparisonTable`
- `BatchIntegrityPanel`
- `MethodologyDiagram`

## 13. Visual direction

The surface operates as a fintech incident-response control room:

- near-black graphite shell and workspace
- phosphor mint for recovered, selected, and authoritative states
- amber for revenue at risk and intervention required
- red only for unresolved outcome, provider failure, or actual error
- thin technical rules
- restrained 4–10px corner radius
- shallow panel depth
- dense but calm information layout
- IBM Plex Sans/system fallback for operational copy
- tabular numerals for money and metrics
- monospace only for IDs, provider references, hashes, and technical versions

Visual emphasis must follow operational priority, not decoration. The interface should feel precise, inspectable, and confident without looking like a generic SaaS dashboard.

## 14. Responsive and accessibility requirements

### Desktop

- persistent sidebar
- dense tables with clear column priority
- two-column layouts for intelligence and provider modules
- Decision Room keeps the case header and next action visible

### Mobile and narrow widths

- collapse sidebar into a compact navigation strip
- stack summary modules
- let dense tables scroll inside their own panel
- preserve amount, status, next action, and case identity before secondary metadata
- preserve accessible action confirmation and error feedback

### Accessibility

- keyboard-accessible navigation, filters, tabs, dialogs, and tables
- visible focus states
- status never communicated by color alone
- semantic table headers
- sufficient contrast in graphite surfaces
- live-region announcements for run status and mutation results
- confirmation dialogs for execution and test actions
- reduced-motion support for run monitors and transitions

## 15. Data and safety requirements

- Frontend renders API-backed fields and permitted aggregates only.
- Frontend never calculates probabilities, expected value, costs, fatigue, constraints, rankings, or selected actions.
- All displayed money uses backend integer paise values and a consistent currency formatter.
- Stored decision data remains immutable in the UI.
- Explanations are append-only history.
- Provider acceptance is not recovery.
- Only persisted, validated recovery outcomes can display `RECOVERED`.
- Live execution must require explicit backend eligibility and clear UI confirmation.
- Demo mode must never silently become live mode.
- LLM provider and model information is shown only when it reflects the actual execution record.
- If the provider is not configured, show `Local deterministic fallback` or `Not configured`; do not infer a vendor from code support.

## 16. Proposed route map

The following is the target conceptual route map. Existing paths may be retained during incremental implementation if that reduces migration risk.

| Current path | Target workspace |
|---|---|
| `/` | Command Center |
| `/cases` | Recovery Operations → Case Queue |
| `/cases?status=DECIDED` | Recovery Operations → Action Queue during migration |
| `/cases/{caseId}` | Decision Room |
| `/intelligence/failures` | Intelligence → Failure Patterns |
| `/intelligence/performance` | Intelligence → Recovery Outcomes |
| `/learn` | Intelligence → Outcome Learning |
| `/audit` | System → Audit Trail |
| `/?view=engine` | System → Decision Engine during migration |
| `/arena` | Evaluation Lab → Recovery Arena |
| `/methodology` | Evaluation Lab → Methodology & Guardrails |
| new | Recovery Operations → Escalations |
| new | Recovery Operations → Scheduled Retries |
| new | System → System Health |
| new | Providers → Provider Readiness |
| new | Evaluation Lab → Demo Scenarios |

## 17. Implementation sequence

Implement as vertical slices so every step remains usable:

### Slice 1: Shell and vocabulary

- sidebar hierarchy
- top bar
- environment/provider mode badges
- breadcrumb behavior
- shared status and loading/error components

### Slice 2: Command Center

- summary metrics
- Needs Attention Now
- recovery pipeline
- system posture
- recent activity
- failure pulse

### Slice 3: Recovery Operations

- Case Queue
- queue summary strip
- filters
- case table
- next-action semantics

### Slice 4: Decision Room

- case header
- diagnosis
- stored decision
- candidates and constraints
- intervention stepper
- execution proof
- outcome
- audit journey

### Slice 5: Operational subqueues

- Action Queue backed by intervention lifecycle
- Escalations
- Scheduled Retries

### Slice 6: Intelligence

- Failure Patterns
- Recovery Outcomes
- Outcome Learning tabs and evidence components

### Slice 7: System

- System Health
- Decision Engine
- Audit Trail

### Slice 8: Providers

- Provider Readiness matrix
- provider detail
- verification history
- safe verification/test affordances

### Slice 9: Evaluation Lab

- Demo Scenarios
- run monitor
- execution proof
- Recovery Arena
- Methodology & Guardrails

### Slice 10: Hardening

- responsive behavior
- empty/loading/error states
- accessibility review
- status vocabulary review
- demo rehearsal with local and test provider modes

## 18. Acceptance criteria

### Global

- Users can identify the current environment and provider mode on every relevant page.
- Navigation labels describe operator work, not backend implementation packages.
- No page claims an external provider action occurred without stored evidence.

### Command Center

- A user can identify revenue at risk and the most urgent next action without opening another page.
- Every summary module deep-links to a source workspace.
- Full analytics and demo controls remain outside the overview.

### Recovery Operations

- A user can filter and scan cases using operational fields.
- Every active row exposes a clear next action.
- Action Queue represents intervention work and lifecycle state.
- Execution actions require backend eligibility and explicit confirmation.

### Decision Room

- A user can follow the case from failure through outcome in one coherent view.
- Stored decision values and candidate statuses are rendered without frontend recomputation.
- Provider receipts, webhook state, and recovery outcome are visibly distinct.
- Optional AI attribution and fallback status are accurate.

### Intelligence

- Every analytical result includes sample-size and observational boundaries.
- Users can move from a pattern or outcome to the underlying cases.
- Recommendations are visibly human-reviewable and non-automatic.

### System and Providers

- Internal system health is separate from external provider readiness.
- Provider modes and verification statuses cannot be confused with recovery outcomes.
- No credentials or unsafe raw provider data are exposed.

### Evaluation Lab

- A reviewer can select a scenario and reach the Decision Room through one clear flow.
- A run shows persisted lifecycle evidence, not simulated UI-only progress.
- Local/demo behavior is explicitly labeled.
- Arena comparisons expose batch integrity and methodology.

## 19. Locked product language

Use:

- `CHIMERA Recovery Agent`
- `Decision authority: deterministic recovery engine`
- `AI assistance: optional; explanations and voice only`
- `Observed outcomes`
- `Provider receipt`
- `Execution proof`
- `Synthetic environment`
- `Local demo provider`
- `Razorpay TEST` when actually connected to Razorpay test mode
- `Demo Voice Agent` for deterministic local voice scenarios

Avoid:

- `LLM-powered payment decision`
- `AI decided to charge the customer`
- `Live` when the provider is local, mock, or test
- `Recovered` when only provider acceptance exists
- `AI learning` when the view is observational analysis
- `Optimization` when the system has not changed policy or model configuration

## 20. Design baseline decision

The UI should make CHIMERA feel like one coherent recovery system:

```text
Command Center       = What is happening now?
Recovery Operations   = What needs work?
Intelligence         = What do the records show?
System               = Is CHIMERA healthy and trustworthy?
Providers            = Can external execution happen safely?
Evaluation Lab       = Can we reproduce and prove the workflow?
```

This structure is the baseline for implementation and should be revisited only if the backend product model changes materially.
