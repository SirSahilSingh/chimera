import Link from "next/link";
import { ArrowRightIcon, CheckIcon, ShieldIcon } from "../../components/icons";
import { IntelligencePanel, IntelligenceTitle } from "../../components/intelligence-workspace";

const boundaries = [
  ["Observe", "CHIMERA receives payment failure context and keeps the customer, payment, amount, method, incident flag, and timestamp visible as stored evidence."],
  ["Estimate", "The model estimates recovery probability from observable context. It does not reveal hidden customer segments or claim a root cause it cannot observe."],
  ["Decide", "The deterministic engine ranks permissible actions using stored costs, fatigue treatment, and policy constraints. Decision authority remains in the backend."],
  ["Intervene", "The orchestrator routes the stored action through a local, mock, test, or explicitly enabled live provider boundary."],
  ["Prove", "Provider receipts, webhook state, and persisted outcomes remain separate. Provider acceptance alone is never shown as recovered revenue."],
] as const;

export default function MethodologyPage() {
  return <div className="evaluation-page methodology-surface">
    <IntelligenceTitle title="Methodology & Guardrails" />
    <div className="workspace-meta standalone-meta"><span>Environment: Evaluation</span><span>Data: Synthetic</span><span>Reviewer-facing trust page</span></div>
    <section className="evaluation-banner"><div><div className="evaluation-banner-icon"><ShieldIcon size={18} /></div><div><strong>Inspect the boundary before the result</strong><p>Evaluation Lab demonstrates a reproducible recovery workflow while keeping every claim tied to a stored record.</p></div></div><span className="methodology-badge">Evidence first</span></section>
    <div className="methodology-flow">{boundaries.map(([title, copy], index) => <div className="methodology-flow-row" key={title}><span>{String(index + 1).padStart(2, "0")}</span><strong>{title}</strong><p>{copy}</p><CheckIcon size={15} /></div>)}</div>
    <div className="methodology-grid-v2"><IntelligencePanel title="Synthetic environment" note="What is simulated"><p>Customers, payment failures, observable history, outcomes, and Arena comparisons are generated from frozen simulator assumptions. No real customer data is used.</p></IntelligencePanel><IntelligencePanel title="AI assistance" note="What is optional"><p>AI may support explanations or the local voice scenario. It is not the financial decision authority and cannot alter a stored decision.</p></IntelligencePanel><IntelligencePanel title="Provider modes" note="What each receipt means"><p>LOCAL, MOCK, and TEST boundaries are safe demonstration modes. Use Razorpay TEST only when a real test provider reference is returned. LIVE requires explicit backend enablement.</p></IntelligencePanel><IntelligencePanel title="What this does not claim" note="Interpretation boundary"><p>These runs do not establish causal performance, production recovery rates, or customer behavior outside the stored synthetic sample.</p></IntelligencePanel></div>
    <div className="methodology-links"><Link href="/demo">Run a demo scenario <ArrowRightIcon size={14} /></Link><Link href="/arena">Compare strategies <ArrowRightIcon size={14} /></Link></div>
  </div>;
}
