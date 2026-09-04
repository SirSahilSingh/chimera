"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import type { SystemHealth } from "../../../lib/types";
import { ArrowRightIcon, CheckIcon, RefreshIcon, ShieldIcon } from "../../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../../components/shell";
import { IntelligencePanel, IntelligenceTitle } from "../../../components/intelligence-workspace";

const pipeline = ["Event", "Context", "Model", "Scoring", "Policy", "Intervention", "Outcome"];

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await api.systemHealth());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load system health.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const operational = health?.status === "ok";

  if (loading) return <div className="system-page"><IntelligenceTitle title="System Health" /><LoadingState label="Checking system health" /></div>;
  if (error || !health) return <div className="system-page"><IntelligenceTitle title="System Health" /><ErrorState message={error ?? "System health is unavailable."} onRetry={load} /></div>;

  return <div className="system-page">
    <IntelligenceTitle title="System Health" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh system health"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More system health actions"><span className="more-dots">•••</span></button></>} />
    <div className="system-health-banner"><div className="system-health-state"><span className={`health-orb ${operational ? "success" : "warning"}`} /><div><strong>{operational ? "CHIMERA operational" : "CHIMERA degraded"}</strong><span>Internal control plane · {health.api_environment.replaceAll("_", " ")}</span></div></div><StatusBadge status={operational ? "OPERATIONAL" : "DEGRADED"} /></div>
    <section className="system-health-grid" aria-label="System health summary"><HealthCell label="API" value="Available" detail="Health endpoint responded" good /><HealthCell label="Database" value={health.database} detail="Connectivity probe" good={health.database === "ok"} /><HealthCell label="Model compatibility" value={health.model_compatibility} detail="Runtime compatibility" good={health.model_compatibility === "compatible"} /><HealthCell label="Environment" value={health.api_environment.replaceAll("_", " ")} detail="Configured API environment" /></section>
    <div className="health-panels"><IntelligencePanel title="Internal pipeline" note="Control boundaries"><div className="system-pipeline">{pipeline.map((stage, index) => <div className="system-pipeline-step" key={stage}><span className="system-pipeline-node"><CheckIcon size={13} /></span><strong>{stage}</strong>{index < pipeline.length - 1 && <ArrowRightIcon size={14} />}</div>)}</div><div className="system-note">The deterministic engine and policy layer remain the decision authority. Optional AI does not sit on the financial decision path.</div></IntelligencePanel><IntelligencePanel title="Safety posture" note="Current operating rules"><div className="safety-list"><SafetyRow text="Backend is the decision authority." /><SafetyRow text="Financial actions are policy validated." /><SafetyRow text="Provider webhooks define outcome evidence." /><SafetyRow text="Live execution requires explicit enablement." /></div></IntelligencePanel></div>
    <div className="system-footnote"><ShieldIcon size={15} /><span>System Health describes CHIMERA itself. External dependency readiness lives under Providers.</span></div>
  </div>;
}

function HealthCell({ label, value, detail, good = true }: { label: string; value: string; detail: string; good?: boolean }) {
  return <div className="health-cell"><div><span className={`health-cell-dot ${good ? "good" : "bad"}`} /><strong>{label}</strong></div><b>{value}</b><small>{detail}</small></div>;
}

function SafetyRow({ text }: { text: string }) {
  return <div className="safety-row"><CheckIcon size={15} /><span>{text}</span></div>;
}
