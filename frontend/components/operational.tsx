"use client";

import Link from "next/link";
import { AlertCircleIcon, ArrowRightIcon, CheckIcon, ClockIcon, ShieldIcon, AlertIcon, ExternalIcon } from "./icons";
import { Button, StatusBadge } from "./shell";
import { formatAction, formatDate, formatFailureReason, formatPaise, formatPercent } from "../lib/formatters";
import { caseDisplayId, isActiveRecovery, isRecovered, isUnresolved, statusLabel } from "../lib/operations";
import type { Candidate, Decision, Execution, JourneyIntervention, RecoveryCase } from "../lib/types";

export function RecoveryLifecycle({ caseData }: { caseData: RecoveryCase }) {
  const decision = Boolean(caseData.latest_decision);
  const execution = Boolean(caseData.latest_execution);
  const recovered = isRecovered(caseData);
  const steps = [
    { label: "Detected", complete: true, detail: `Payment failure recorded at ${formatDate(caseData.created_at)}.` },
    { label: "Diagnosed", complete: decision, detail: decision ? "Observable context scored by the deterministic engine." : "Awaiting a stored deterministic decision." },
    { label: "Decision made", complete: decision, detail: decision ? `${formatAction(caseData.latest_decision!.selected_action)} selected by the stored trace.` : "No decision has been persisted." },
    { label: "Intervention", complete: execution, detail: execution ? `${formatAction(caseData.latest_execution!.action)} execution record is present.` : "Awaiting an eligible intervention." },
    { label: "Recovered", complete: recovered, detail: recovered ? "The backend reports a recovered case." : caseData.status === "UNRECOVERED" ? "The backend reports an unresolved outcome." : "Outcome pending; no recovery claim is shown." },
  ];
  return <section className="lifecycle-panel" aria-label="Recovery journey">
    <div className="panel-heading"><div><span className="section-overline">Recovery journey</span><h2>Detect → Diagnose → Decide → Intervene → Recover</h2></div><StatusBadge status={caseData.status} /></div>
    <div className="lifecycle-track">{steps.map((step, index) => <details className={`lifecycle-step ${step.complete ? "complete" : "pending"}`} key={step.label} open={index === 0 || (step.complete && index === steps.findIndex((item) => !item.complete))}>
      <summary><span className="lifecycle-node">{step.complete ? <CheckIcon size={13} /> : <span>{index + 1}</span>}</span><span>{step.label}</span></summary>
      <p>{step.detail}</p>
    </details>)}</div>
  </section>;
}

export function FailureDiagnosis({ caseData, decision }: { caseData: RecoveryCase; decision: Decision | null }) {
  return <section className="diagnosis-panel dark-panel">
    <div className="panel-heading"><h2>Payment failure detected</h2><div className="diagnosis-meta"><strong>{formatPaise(caseData.amount_paise, caseData.currency)}</strong><span>{formatDate(caseData.created_at)}</span></div></div>
    <div className="diagnosis-main"><div className="diagnosis-mark"><AlertCircleIcon size={24} /></div><div className="diagnosis-copy"><strong>{formatFailureReason(caseData.failure_reason)}</strong><p>Failure recorded at decision time with the observable payment context attached.</p></div><div className="diagnosis-main-facts"><div><span>Payment method</span><strong>{caseData.payment_method.toUpperCase()}</strong></div><div><span>Stored response</span><strong>{decision ? formatAction(decision.selected_action) : "Awaiting decision"}</strong></div></div></div>
  </section>;
}

export function CandidateActionComparison({ decision, currency = "INR" }: { decision: Decision; currency?: string }) {
  const ordered = [...decision.candidates].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  return <section className="candidate-panel"><div className="panel-heading"><div><span className="section-overline">Decide</span><h2>How CHIMERA chose the intervention</h2></div></div><div className="candidate-list">{ordered.map((candidate) => <article className={`candidate-card ${candidate.action === decision.selected_action ? "selected" : ""} ${candidate.status !== "PERMISSIBLE" ? "blocked" : ""}`} key={candidate.action}>
    <div className="candidate-rank">{candidate.rank ?? "—"}</div><div className="candidate-copy"><div className="candidate-card-title"><strong>{formatAction(candidate.action)}</strong>{candidate.action === decision.selected_action && <span className="selected-chip"><CheckIcon size={12} />Selected</span>}{candidate.status !== "PERMISSIBLE" && <span className="blocked-chip"><AlertIcon size={12} />Blocked</span>}</div><div className="candidate-bar"><span style={{ width: `${Math.max(4, Math.min(100, candidate.predicted_probability * 100))}%` }} /></div><div className="candidate-meta"><span><small>Predicted recovery</small><strong>{formatPercent(candidate.predicted_probability)}</strong></span><span><small>Action cost</small><strong>{formatPaise(candidate.action_cost_paise, currency)}</strong></span><span><small>Fatigue</small><strong>{formatPaise(candidate.fatigue_penalty_paise, currency)}</strong></span></div>{candidate.status !== "PERMISSIBLE" && <p className="blocked-reason">{candidate.blocked_reason?.replaceAll("_", " ") ?? "Unavailable under stored policy."}</p>}</div><div className="candidate-arrow">{candidate.action === decision.selected_action ? <CheckIcon size={17} /> : <ArrowRightIcon size={16} />}</div>
  </article>)}</div></section>;
}

export function DecisionReasoning({ decision, explanation }: { decision: Decision; explanation?: { structured_explanation: { summary: string; recommendation: { reason: string }; key_factors: { factor: string; impact: string }[] } } | null }) {
  const highestProbability = typeof decision.trace_json.highest_probability_action === "string" ? decision.trace_json.highest_probability_action : null;
  return <section className="reasoning-panel"><div className="panel-heading"><div><span className="section-overline">Decision reasoning</span><h2>Probability ≠ decision</h2></div><span className="source-line"><span className="status-dot mint-dot" />Explanation generated from stored decision trace</span></div><div className="reasoning-grid"><div className="reasoning-formula"><div className="formula-row"><span>Predicted recovery</span><strong>{formatPercent(decision.predicted_probability)}</strong></div><div className="formula-row minus"><span>Intervention + fatigue cost</span><strong>Applied</strong></div><div className="formula-row minus"><span>Policy constraints</span><strong>Validated</strong></div><div className="formula-result"><span>Selected action</span><strong>{formatAction(decision.selected_action)}</strong><b>{formatAction(decision.selected_action)}</b></div></div><div className="reasoning-copy">{explanation ? <><p className="reasoning-summary">{explanation.structured_explanation.summary}</p><p>{explanation.structured_explanation.recommendation.reason}</p></> : <p>The deterministic engine selected the highest permissible action after applying intervention cost, fatigue, and stored policy constraints.</p>}{highestProbability && highestProbability !== decision.selected_action && <div className="comparison-callout"><span>Highest raw probability</span><strong>{formatAction(highestProbability)}</strong><small>The winner changed after economics and policy validation.</small></div>}</div></div></section>;
}

export function ConstraintList({ decision }: { decision: Decision }) {
  const blocked = decision.candidates.filter((candidate) => candidate.status !== "PERMISSIBLE");
  const selected = decision.candidates.find((candidate) => candidate.action === decision.selected_action);
  return <section className="constraints-panel"><div className="panel-heading"><div><span className="section-overline">Policy guardrails</span><h2>Decision rules applied</h2></div><ShieldIcon size={18} /></div><div className="constraint-list"><div className="constraint-row positive"><CheckIcon size={15} /><span>Selected action is permissible under the stored policy.</span><strong>{formatAction(decision.selected_action)}</strong></div>{selected && <div className="constraint-row positive"><CheckIcon size={15} /><span>Fatigue treatment included in action scoring.</span><strong>{formatPaise(selected.fatigue_penalty_paise)}</strong></div>}{blocked.map((candidate) => <div className="constraint-row blocked" key={candidate.action}><AlertIcon size={15} /><span>{formatAction(candidate.action)} unavailable</span><strong>{candidate.blocked_reason?.replaceAll("_", " ") ?? "Policy blocked"}</strong></div>)}</div></section>;
}

export function InterventionStatus({ caseData, decision, execution, journeyIntervention, canExecute, onExecute }: { caseData: RecoveryCase; decision: Decision; execution: Execution | null; journeyIntervention: JourneyIntervention | null; canExecute: boolean; onExecute: () => void }) {
  const journeyExecution = journeyIntervention?.executions.at(-1) ?? null;
  const displayedExecution = execution ?? journeyExecution;
  const displayedStatus = displayedExecution?.status ?? journeyIntervention?.status;
  return <section className="intervention-panel dark-panel"><div className="panel-heading"><div><span className="section-overline">Intervene</span><h2>CHIMERA action</h2></div>{displayedStatus ? <StatusBadge status={displayedStatus} /> : <span className="signal-chip warning"><span />Awaiting intervention</span>}</div>{displayedExecution ? <div className="intervention-result"><div><span className="intervention-action">{formatAction(displayedExecution.action ?? journeyIntervention?.action ?? decision.selected_action)}</span><p>Stored execution record. Idempotency protection remains with the backend.</p></div><div className="intervention-details"><div><span>Provider reference</span><strong>{displayedExecution.provider_reference ?? "Not returned"}</strong></div><div><span>Executed at</span><strong>{displayedExecution.executed_at ? formatDate(displayedExecution.executed_at) : "Pending timestamp"}</strong></div></div></div> : <div className="intervention-wait"><div><span className="intervention-action">{formatAction(decision.selected_action)}</span><p>is the stored action for this case. Execution is available only while the backend reports <b>DECIDED</b>.</p></div><Button onClick={onExecute} disabled={!canExecute}>{canExecute ? "Execute stored action" : `Unavailable in ${statusLabel(caseData.status)}`}<ArrowRightIcon size={15} /></Button></div>}</section>;
}

export function RecoveryOutcome({ caseData }: { caseData: RecoveryCase }) {
  const recovered = isRecovered(caseData);
  const unresolved = caseData.status === "UNRECOVERED";
  return <section className={`outcome-panel ${recovered ? "recovered" : unresolved ? "unresolved" : "pending"}`}><div className="outcome-icon">{recovered ? <CheckIcon size={20} /> : unresolved ? <AlertIcon size={20} /> : <ClockIcon size={20} />}</div><div><span className="section-overline">Recover</span><h2>{recovered ? "Recovered" : unresolved ? "Unresolved" : "Recovery in progress"}</h2><p>{recovered ? `The backend reports ${formatPaise(caseData.amount_paise, caseData.currency)} recovered.` : unresolved ? "No recovery outcome was recorded for this case." : "Outcome pending; recovery is still in progress."}</p></div><StatusBadge status={caseData.status} /></section>;
}

type ActivityEvent = { label: string; detail: string; timestamp: string; tone?: "mint" | "amber" | "red" };
export function RecoveryActivityFeed({ cases, caseData, decision, execution }: { cases?: RecoveryCase[]; caseData?: RecoveryCase; decision?: Decision | null; execution?: Execution | null }) {
  const events: ActivityEvent[] = [];
  if (caseData) {
    events.push({ label: "Payment failure detected", detail: `${formatFailureReason(caseData.failure_reason)} · ${formatPaise(caseData.amount_paise, caseData.currency)}`, timestamp: caseData.created_at, tone: "amber" });
    if (decision) events.push({ label: "Decision persisted", detail: `${formatAction(decision.selected_action)} selected after policy validation`, timestamp: decision.created_at, tone: "mint" });
    if (execution) events.push({ label: "Action executed", detail: `${formatAction(execution.action)} · ${execution.provider_reference ?? "No provider reference"}`, timestamp: execution.executed_at ?? execution.created_at, tone: "mint" });
    if (isRecovered(caseData) || caseData.status === "UNRECOVERED") events.push({ label: "Outcome status recorded", detail: statusLabel(caseData.status), timestamp: caseData.updated_at, tone: isRecovered(caseData) ? "mint" : "red" });
  } else {
    for (const item of cases ?? []) {
      events.push({ label: `${statusLabel(item.status)} · ${caseDisplayId(item)}`, detail: `${formatFailureReason(item.failure_reason)} · ${formatPaise(item.amount_paise, item.currency)}`, timestamp: item.updated_at, tone: isActiveRecovery(item) ? "amber" : isRecovered(item) ? "mint" : undefined });
    }
  }
  events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  return <section className="activity-panel"><div className="panel-heading"><div><span className="section-overline">Live recovery activity</span><h2>CHIMERA in action</h2></div><span className="panel-note">Stored events only</span></div>{events.length ? <div className="activity-feed">{events.map((event, index) => <div className="activity-event" key={`${event.label}-${event.timestamp}-${index}`}><span className={`activity-marker ${event.tone ?? ""}`} /><div className="activity-copy"><strong>{event.label}</strong><p>{event.detail}</p></div><time>{formatDate(event.timestamp)}</time></div>)}</div> : <div className="inline-empty"><ExternalIcon size={16} /><span>No stored activity is available yet.</span></div>}</section>;
}

type Breakdown = { reason: string; cases: number; amount: number; recovered: number; decided: number };
function buildBreakdown(cases: RecoveryCase[]) {
  const map = new Map<string, Breakdown>();
  for (const item of cases) {
    const current = map.get(item.failure_reason) ?? { reason: item.failure_reason, cases: 0, amount: 0, recovered: 0, decided: 0 };
    current.cases += 1; current.amount += item.amount_paise; current.recovered += isRecovered(item) ? 1 : 0; current.decided += item.latest_decision ? 1 : 0; map.set(item.failure_reason, current);
  }
  return Array.from(map.values()).sort((a, b) => b.amount - a.amount);
}

export function FailureBreakdown({ cases }: { cases: RecoveryCase[] }) {
  const breakdown = buildBreakdown(cases);
  return <section className="breakdown-panel"><div className="panel-heading"><div><span className="section-overline">Failure intelligence</span><h2>Payment failure breakdown</h2></div><span className="panel-note">Observed case distribution</span></div>{breakdown.length ? <div className="breakdown-list">{breakdown.map((item) => <Link href={`/cases?failure_reason=${encodeURIComponent(item.reason)}`} className="breakdown-row" key={item.reason}><div className="breakdown-name"><span className="breakdown-dot" /><strong>{formatFailureReason(item.reason)}</strong><small>{item.cases} {item.cases === 1 ? "case" : "cases"}</small></div><div className="breakdown-bar"><span style={{ width: `${Math.max(4, (item.amount / Math.max(...breakdown.map((entry) => entry.amount))) * 100)}%` }} /></div><div className="breakdown-value"><strong>{formatPaise(item.amount)}</strong><small>{item.recovered ? `${formatPercent(item.recovered / item.cases)} recovered` : "No recovered status"}</small></div><ArrowRightIcon size={15} /></Link>)}</div> : <div className="inline-empty"><ExternalIcon size={16} /><span>Failure distribution will appear when cases are stored.</span></div>}</section>;
}

export function RootCauseInsight({ cases }: { cases: RecoveryCase[] }) {
  const breakdown = buildBreakdown(cases).slice(0, 3);
  return <section className="root-cause-panel"><div className="panel-heading"><div><span className="section-overline">Root cause intelligence</span><h2>Why payments are failing</h2></div><span className="panel-note">Observed patterns, not hidden truth</span></div>{breakdown.length ? <div className="root-cause-list">{breakdown.map((item) => { const sample = cases.find((candidate) => candidate.failure_reason === item.reason); return <div className="root-cause-row" key={item.reason}><div><span className="pattern-label">Observed failure pattern</span><strong>{formatFailureReason(item.reason)}</strong></div><div><span>Impact</span><strong>{formatPaise(item.amount)}</strong></div><div><span>Affected</span><strong>{item.cases}</strong></div><div><span>CHIMERA response</span><strong>{sample?.latest_decision ? formatAction(sample.latest_decision.selected_action) : "Awaiting decision"}</strong></div><StatusBadge status={sample?.status ?? "NEW"} /></div>; })}</div> : <div className="inline-empty"><ExternalIcon size={16} /><span>No observed failure patterns are available yet.</span></div>}</section>;
}

export function InterventionPerformance({ cases }: { cases: RecoveryCase[] }) {
  const rows = new Map<string, { action: string; cases: number; recovered: number; value: number }>();
  for (const item of cases) {
    const action = item.latest_decision?.selected_action;
    if (!action) continue;
    const row = rows.get(action) ?? { action, cases: 0, recovered: 0, value: 0 };
    row.cases += 1; row.recovered += isRecovered(item) ? 1 : 0; row.value += isRecovered(item) ? item.amount_paise : 0; rows.set(action, row);
  }
  const values = Array.from(rows.values()).sort((a, b) => b.value - a.value);
  return <section className="performance-panel"><div className="panel-heading"><div><span className="section-overline">Recovery performance</span><h2>Observed intervention outcomes</h2></div><span className="panel-note">Not causal evidence</span></div>{values.length ? <div className="performance-list">{values.map((row) => <div className="performance-row" key={row.action}><div><strong>{formatAction(row.action)}</strong><span>{row.cases} {row.cases === 1 ? "case" : "cases"}</span></div><div><span>Observed recovery rate</span><strong>{formatPercent(row.recovered / row.cases)}</strong></div><div><span>Recovered value</span><strong>{formatPaise(row.value)}</strong></div></div>)}</div> : <div className="inline-empty"><ExternalIcon size={16} /><span>Intervention performance will appear after stored decisions and outcomes.</span></div>}</section>;
}

const stageOrder = ["NEW", "DECIDED", "ACTION_PENDING", "ACTION_EXECUTED", "PROMISE_TO_PAY_PENDING", "RECOVERED", "UNRECOVERED"];
const actionOrder = ["RETRY_NOW", "RETRY_LATER", "PAYMENT_LINK", "SEND_MESSAGE", "VOICE_RECOVERY", "ESCALATE", "DO_NOTHING"];

export function OperationsDistribution({ cases }: { cases: RecoveryCase[] }) {
  if (!cases.length) return <section className="distribution-panel"><div className="inline-empty"><ExternalIcon size={16} /><span>Stage and intervention distribution will appear when cases are stored.</span></div></section>;
  const stages = stageOrder.map((status) => ({ label: statusLabel(status), count: cases.filter((item) => item.status === status).length })).filter((item) => item.count);
  const actions = actionOrder.map((action) => ({ label: formatAction(action), count: cases.filter((item) => item.latest_decision?.selected_action === action).length })).filter((item) => item.count);
  const maxStage = Math.max(...stages.map((item) => item.count), 1);
  const maxAction = Math.max(...actions.map((item) => item.count), 1);
  return <section className="distribution-panel"><div className="panel-heading"><div><span className="section-overline">Stored operating state</span><h2>Where the money is in the journey</h2></div><span className="panel-note">Loaded persisted cases · {cases.length} total</span></div><div className="distribution-grid"><div><div className="distribution-subhead"><strong>Case stages</strong><span>Current status</span></div>{stages.length ? stages.map((item) => <div className="distribution-row" key={item.label}><span>{item.label}</span><div><i style={{ width: `${(item.count / maxStage) * 100}%` }} /></div><strong>{item.count}</strong></div>) : <div className="distribution-empty">No lifecycle statuses recorded.</div>}</div><div><div className="distribution-subhead"><strong>Selected interventions</strong><span>Stored decisions</span></div>{actions.length ? actions.map((item) => <div className="distribution-row action-distribution" key={item.label}><span>{item.label}</span><div><i style={{ width: `${(item.count / maxAction) * 100}%` }} /></div><strong>{item.count}</strong></div>) : <div className="distribution-empty">No decisions recorded yet.</div>}</div></div></section>;
}
