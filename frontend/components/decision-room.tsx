"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "../lib/api";
import { caseDisplayId } from "../lib/operations";
import { formatAction, formatDate, formatPaise } from "../lib/formatters";
import type { Decision, Explanation, Execution, RecoveryCase, RecoveryIntelligence, RecoveryJourney } from "../lib/types";
import { AlertIcon, ArrowRightIcon, CheckIcon, ChevronDownIcon, ClockIcon, ExternalIcon, RefreshIcon, ShieldIcon, XIcon } from "./icons";
import { Button, ErrorState, StatusBadge } from "./shell";
import { CandidateActionComparison, ConstraintList, DecisionReasoning, FailureDiagnosis, InterventionStatus, RecoveryLifecycle, RecoveryOutcome } from "./operational";
import { PersistedJourneyTimeline, ProviderJourney } from "./recovery-journey";
import { RecoveryIntelligenceNarrative } from "./recovery-intelligence";

export function DecisionRoom({ initialCase }: { initialCase: RecoveryCase }) {
  const [caseData, setCaseData] = useState(initialCase);
  const [busy, setBusy] = useState<"decide" | "execute" | "explain" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [history, setHistory] = useState<Explanation[]>([]);
  const [journey, setJourney] = useState<RecoveryJourney | null>(null);
  const [intelligence, setIntelligence] = useState<RecoveryIntelligence | null>(null);
  const decision = caseData.latest_decision;

  const refresh = async () => {
    const nextCase = await api.getCase(caseData.id);
    setCaseData(nextCase);
    const [journeyResult, intelligenceResult] = await Promise.allSettled([api.getJourney(caseData.id), api.getIntelligence(caseData.id)]);
    setJourney(journeyResult.status === "fulfilled" ? journeyResult.value : null);
    setIntelligence(intelligenceResult.status === "fulfilled" ? intelligenceResult.value : null);
  };
  useEffect(() => {
    setJourney(null); setIntelligence(null);
    Promise.allSettled([api.getJourney(caseData.id), api.getIntelligence(caseData.id)]).then(([journeyResult, intelligenceResult]) => {
      setJourney(journeyResult.status === "fulfilled" ? journeyResult.value : null);
      setIntelligence(intelligenceResult.status === "fulfilled" ? intelligenceResult.value : null);
    });
  }, [caseData.id]);
  useEffect(() => {
    if (!decision) return;
    api.getLatestExplanation(decision.id).then(setExplanation).catch(() => undefined);
    api.getExplanationHistory(decision.id).then(setHistory).catch(() => undefined);
  }, [decision?.id]);

  const run = async (kind: "decide" | "execute" | "explain") => {
    setBusy(kind); setError(null);
    try {
      if (kind === "decide") { await api.decide(caseData.id); await refresh(); }
      if (kind === "execute") { await api.execute(caseData.id); await refresh(); }
      if (kind === "explain" && decision) { const next = await api.explain(decision.id); setExplanation(next); setHistory((current) => [next, ...current]); }
    } catch (err) { setError(err instanceof ApiError ? err.detail : "The operation could not be completed."); }
    finally { setBusy(null); setConfirmOpen(false); }
  };

  const canExecute = caseData.status === "DECIDED" && Boolean(decision);
  return <div className="decision-room">
    <div className="detail-hero">
      <div>
        <Link href="/cases" className="backline">← Recovery operations</Link>
        <div className="detail-title"><div><span className="detail-overline">Case</span><h1>{caseDisplayId(caseData)}</h1><p>{caseData.id} · {caseData.customer_id}</p></div><StatusBadge status={caseData.status} /></div>
      </div>
      <div className="detail-actions">{!decision && <Button onClick={() => run("decide")} disabled={busy !== null}><ShieldIcon size={16} />{busy === "decide" ? "Generating…" : "Generate decision"}</Button>}{canExecute && <Button kind="secondary" onClick={() => setConfirmOpen(true)} disabled={busy !== null}><ArrowRightIcon size={16} />Execute action</Button>}<Button kind="quiet" onClick={refresh} disabled={busy !== null} aria-label="Refresh case"><RefreshIcon size={16} /></Button></div>
      <div className="risk-readout"><span>Revenue at risk</span><strong>{formatPaise(caseData.amount_paise, caseData.currency)}</strong><small>Payment {caseData.payment_id} · {formatDate(caseData.decision_timestamp)}</small></div>
    </div>
    {error && <ErrorState message={error} onRetry={() => setError(null)} />}
    <RecoveryLifecycle caseData={caseData} />
    {intelligence ? <RecoveryIntelligenceNarrative intelligence={intelligence} /> : <section className="intelligence-narrative intelligence-loading"><div className="inline-empty"><span className="loader" /><span>Loading case intelligence…</span></div></section>}
    <div className="detail-grid"><FailureDiagnosis caseData={caseData} decision={decision} />{decision ? <DecisionReasoning decision={decision} explanation={explanation} /> : <DecisionEmpty busy={busy === "decide"} onDecide={() => run("decide")} />}</div>
    {decision ? <>
      <CandidateActionComparison decision={decision} currency={caseData.currency} />
      <div className="detail-grid lower"><ExplanationSection decision={decision} explanation={explanation} history={history} busy={busy === "explain"} onExplain={() => run("explain")} /><ConstraintList decision={decision} /></div>
      <div className="detail-grid lower"><InterventionStatus caseData={caseData} decision={decision} execution={caseData.latest_execution} canExecute={canExecute} onExecute={() => setConfirmOpen(true)} /><RecoveryOutcome caseData={caseData} /></div>
    {journey ? <><ProviderJourney journey={journey} /><PersistedJourneyTimeline journey={journey} /></> : <section className="journey-panel"><div className="inline-empty"><span className="loader" /><span>Loading persisted recovery journey…</span></div></section>}
    </> : <div className="detail-grid lower"><RecoveryOutcome caseData={caseData} /></div>}
    {confirmOpen && decision && <ConfirmDialog caseData={caseData} decision={decision} onCancel={() => setConfirmOpen(false)} onConfirm={() => run("execute")} busy={busy === "execute"} />}
  </div>;
}

function DecisionEmpty({ busy, onDecide }: { busy: boolean; onDecide: () => void }) {
  return <section className="decision-empty dark-panel"><div className="empty-orbit"><ShieldIcon size={21} /></div><div><span className="section-overline">Decide</span><h2>Decision not generated</h2><p>CHIMERA will score the observable case context and persist the authoritative candidate trace.</p></div><Button onClick={onDecide} disabled={busy}>{busy ? "Generating decision…" : "Generate stored decision"}<ArrowRightIcon size={15} /></Button></section>;
}

function ExplanationSection({ decision, explanation, history, busy, onExplain }: { decision: Decision; explanation: Explanation | null; history: Explanation[]; busy: boolean; onExplain: () => void }) {
  const [showHistory, setShowHistory] = useState(false);
  return <section className="explanation-panel"><div className="panel-heading"><div><span className="section-overline">Explain</span><h2>Decision explanation</h2></div><Button kind="secondary" onClick={onExplain} disabled={busy}>{busy ? "Generating…" : explanation ? "Generate new explanation" : "Generate explanation"}<ArrowRightIcon size={15} /></Button></div>{explanation ? <><div className="explanation-main"><div className="explanation-source"><span className={`source-badge ${explanation.explanation_source}`}><span className="status-dot" />{explanation.explanation_source === "fallback" ? "Deterministic fallback" : "AI explanation"}</span><time>{formatDate(explanation.generated_at)}</time></div><p className="explanation-summary">{explanation.structured_explanation.summary}</p><div className="explanation-reason"><span>Why {formatAction(decision.selected_action)}</span><strong>{explanation.structured_explanation.recommendation.reason}</strong></div><div className="factor-list">{explanation.structured_explanation.key_factors.map((factor) => <div className="factor-row" key={factor.factor}><CheckIcon size={14} /><strong>{factor.factor}</strong><span>{factor.impact}</span></div>)}</div><div className="explanation-foot"><span>{explanation.provider} · {explanation.model_name}</span><span>{explanation.prompt_version}</span>{explanation.fallback_reason && <span className="fallback-reason">Fallback: {explanation.fallback_reason.replaceAll("_", " ")}</span>}</div></div><button className="history-toggle" onClick={() => setShowHistory((value) => !value)}><ClockIcon size={15} />Explanation history <span>{history.length}</span><ChevronDownIcon size={15} /></button>{showHistory && <div className="history-list">{history.map((item) => <div className="history-row" key={item.id}><span className={`history-source ${item.explanation_source}`} /><span>{formatDate(item.generated_at)}</span><strong>{item.explanation_source === "fallback" ? "Deterministic fallback" : item.provider}</strong><span>{item.explanation_version}</span></div>)}</div>}</> : <div className="explanation-empty"><div className="empty-orbit"><ExternalIcon size={17} /></div><div><strong>No explanation generated</strong><p>The deterministic decision is complete. Explanations are informational and optional.</p></div><span className="optional-note">Optional</span></div>}</section>;
}

function ConfirmDialog({ caseData, decision, onCancel, onConfirm, busy }: { caseData: RecoveryCase; decision: Decision; onCancel: () => void; onConfirm: () => void; busy: boolean }) {
  return <div className="dialog-backdrop" role="presentation"><div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><button className="dialog-close" onClick={onCancel} aria-label="Close confirmation"><XIcon size={18} /></button><div className="dialog-icon"><ShieldIcon size={20} /></div><span className="section-overline">Backend-authorized action</span><h2 id="confirm-title">Execute stored decision?</h2><p>The browser will submit the existing decision. It will not recalculate, alter, or replace the selected action.</p><div className="confirm-details"><div><span>Case</span><strong>{caseDisplayId(caseData)}</strong></div><div><span>Action</span><strong>{formatAction(decision.selected_action)}</strong></div><div><span>Expected net</span><strong>{formatPaise(decision.expected_net_value_paise, caseData.currency)}</strong></div></div><div className="dialog-actions"><Button kind="quiet" onClick={onCancel}>Cancel</Button><Button onClick={onConfirm} disabled={busy}>{busy ? "Executing…" : "Confirm execution"}<ArrowRightIcon size={15} /></Button></div></div></div>;
}
