"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRightIcon, CheckIcon, FlaskIcon, RefreshIcon, ShieldIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle } from "../../components/intelligence-workspace";
import { api, ApiError } from "../../lib/api";
import { formatAction, formatDate, formatPaise, shortId } from "../../lib/formatters";
import type { DemoRunResponse, RecoveryJourney } from "../../lib/types";

const scenarios = [
  { value: "payment_recovery", label: "Payment Recovery", summary: "Expired method → synthetic payment link", setup: "An observable payment failure with an expired payment method.", evidence: "Payment link, provider receipt, and outcome state", icon: ShieldIcon },
  { value: "voice_recovery", label: "Voice-Assisted Recovery", summary: "Customer requests a link through Demo Voice Agent", setup: "A payment failure routed through a deterministic local voice flow.", evidence: "Transcript turns, detected intent, and resulting payment link", icon: FlaskIcon },
] as const;

type ScenarioValue = (typeof scenarios)[number]["value"];

export default function DemoScenariosPage() {
  const [selected, setSelected] = useState<ScenarioValue>("payment_recovery");
  const [run, setRun] = useState<DemoRunResponse | null>(null);
  const [journey, setJourney] = useState<RecoveryJourney | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const selectedScenario = scenarios.find((scenario) => scenario.value === selected) ?? scenarios[0];

  const launch = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.runDemo({ scenario: selected, provider_mode: "LOCAL" });
      const persistedJourney = await api.getJourney(result.case_id);
      setRun(result);
      setJourney(persistedJourney);
      setNotice("Run completed from persisted backend records.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The scenario could not be run.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="evaluation-page">
    <IntelligenceTitle title="Demo Scenarios" action={<button className="square-control" type="button" onClick={() => { setRun(null); setJourney(null); setNotice(null); }} disabled={!run} aria-label="Clear demo run"><RefreshIcon size={16} /></button>} />
    <section className="evaluation-banner"><div><div className="evaluation-banner-icon"><FlaskIcon size={18} /></div><div><strong>Show the recovery agent at work</strong><p>Select a controlled scenario, run it through the real decision and provider boundaries, then inspect the evidence in Decision Room.</p></div></div><StatusBadge status="LOCAL" /></section>

    <section className="scenario-grid" aria-label="Demo scenarios">{scenarios.map((scenario) => { const Icon = scenario.icon; return <button type="button" className={`scenario-card ${selected === scenario.value ? "selected" : ""}`} onClick={() => setSelected(scenario.value)} key={scenario.value}><div className="scenario-card-head"><span className="scenario-icon"><Icon size={17} /></span>{selected === scenario.value && <span className="scenario-selected"><CheckIcon size={13} />Selected</span>}</div><strong>{scenario.label}</strong><span>{scenario.summary}</span><small>{scenario.setup}</small><em>{scenario.evidence}</em></button>; })}</section>

    <section className="scenario-setup"><div><h2>{selectedScenario.label}</h2><p>{selectedScenario.setup}</p></div><div className="scenario-setup-actions"><Link className="demo-checkout-link" href="/checkout">Use a real Razorpay checkout <ArrowRightIcon size={14} /></Link><button className="button button-primary" type="button" onClick={launch} disabled={busy}>{busy ? "Running scenario…" : "Run scenario"}<ArrowRightIcon size={15} /></button></div></section>
    {error && <ErrorState message={error} onRetry={launch} />}
    {busy && <div className="demo-monitor-loading"><LoadingState label="Waiting for persisted recovery evidence" /></div>}
    {notice && !busy && <div className="queue-notice" role="status"><CheckIcon size={15} /><span>{notice}</span></div>}
    {run && journey && !busy && <RunMonitor run={run} journey={journey} />}
  </div>;
}

function RunMonitor({ run, journey }: { run: DemoRunResponse; journey: RecoveryJourney }) {
  const hasProviderAction = Boolean(journey.payments.length || journey.messages.length || journey.retries.length || journey.scheduled_retries.length || journey.voice_calls.length || journey.escalations.length);
  const recovered = journey.case.status === "RECOVERED";
  const stages = [
    { label: "Failure received", complete: true, detail: `${journey.case.failure_reason.replaceAll("_", " ")} · ${formatDate(journey.case.created_at)}` },
    { label: "Decision created", complete: Boolean(journey.decision), detail: journey.decision ? `${formatAction(journey.decision.selected_action)} selected · ${formatDate(journey.decision.created_at)}` : "No stored decision" },
    { label: "Intervention authorized", complete: Boolean(journey.interventions.length), detail: journey.interventions.length ? `${formatAction(journey.interventions[0].action)} · ${formatDate(journey.interventions[0].created_at)}` : "No stored intervention" },
    { label: "Provider action", complete: hasProviderAction, detail: hasProviderAction ? `${run.provider_mode_label} · persisted receipt available` : "No provider action recorded" },
    { label: "Outcome", complete: recovered || journey.case.status === "UNRECOVERED", detail: recovered ? "Recovered outcome is persisted" : journey.case.status === "UNRECOVERED" ? "Unresolved outcome is persisted" : "Outcome remains pending" },
  ];
  return <section className="run-monitor"><div className="run-monitor-head"><div><h2>Persisted run</h2><p>{run.scenario.replaceAll("_", " ")} · case {shortId(run.case_id)}</p></div><div className="run-monitor-actions"><StatusBadge status={run.current_status} /><Link className="button button-secondary" href={`/cases/${run.case_id}`}>Open Decision Room <ArrowRightIcon size={14} /></Link></div></div><div className="run-stage-list">{stages.map((stage) => <div className={`run-stage ${stage.complete ? "complete" : "pending"}`} key={stage.label}><span className="run-stage-mark">{stage.complete ? <CheckIcon size={14} /> : <span />}</span><div><strong>{stage.label}</strong><span>{stage.detail}</span></div></div>)}</div><div className="run-proof-grid"><RunProof run={run} journey={journey} /><RunEvidence journey={journey} /></div></section>;
}

function RunProof({ run, journey }: { run: DemoRunResponse; journey: RecoveryJourney }) {
  const payment = journey.payments[0];
  const voice = journey.voice_calls[0];
  const schedule = journey.scheduled_retries[0];
  const escalation = journey.escalations[0];
  return <IntelligencePanel title="Execution proof" note="Stored provider boundary"><div className="run-proof-list"><div><span>Selected action</span><strong>{formatAction(run.selected_action)}</strong></div><div><span>Provider mode</span><strong>{run.provider_mode_label}</strong></div>{payment && <div><span>Payment link</span><strong>{payment.status} · {payment.provider}</strong><small>{payment.short_url}</small></div>}{voice && <div><span>Voice boundary</span><strong>Demo Voice Agent · {voice.status}</strong><small>{voice.provider_call_reference ?? "No external call reference"}</small></div>}{schedule && <div><span>Retry schedule</span><strong>{schedule.execution_status}</strong><small>Scheduled {formatDate(schedule.scheduled_at)}</small></div>}{escalation && <div><span>Operator review</span><strong>{escalation.status} · P{escalation.priority}</strong><small>{escalation.reason}</small></div>}</div></IntelligencePanel>;
}

function RunEvidence({ journey }: { journey: RecoveryJourney }) {
  return <IntelligencePanel title="Run evidence" note="No UI-only progress"><div className="run-proof-list"><div><span>Case created</span><strong>{formatDate(journey.case.created_at)}</strong></div><div><span>Audit events</span><strong>{journey.audit_trail.length}</strong></div><div><span>Decision reference</span><strong>{journey.decision ? shortId(journey.decision.id) : "Not recorded"}</strong></div><div><span>Current case state</span><strong>{journey.case.status.replaceAll("_", " ")}</strong></div></div><div className="run-evidence-note"><ShieldIcon size={14} /><span>Every stage above is derived from the recovery journey returned by the backend.</span></div></IntelligencePanel>;
}
