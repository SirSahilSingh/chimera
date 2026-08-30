"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "../../../lib/api";
import type { Decision, RecoveryCase } from "../../../lib/types";
import { formatAction, formatDate, formatPaise, formatPercent } from "../../../lib/formatters";
import { ArrowRightIcon, CheckIcon, RefreshIcon, ShieldIcon } from "../../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../../components/shell";
import { IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../../components/intelligence-workspace";

export default function DecisionEnginePage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listCases({ page: 1, pageSize: 100 });
      setCases(response.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load decision engine provenance.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const decisions = useMemo(() => cases.map((item) => item.latest_decision).filter((item): item is Decision => Boolean(item)), [cases]);
  const latest = decisions.slice().sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ?? null;
  const versions = latest ? [
    ["Engine version", latest.engine_version],
    ["Model version", latest.model_version],
    ["Feature schema", latest.feature_schema_version],
    ["Simulator version", latest.simulator_version ?? "Not recorded"],
    ["Policy", traceValue(latest, "policy_version")],
    ["Tie-breaking", traceValue(latest, "tie_breaking")],
  ] : [];

  if (loading) return <div className="system-page"><IntelligenceTitle title="Decision Engine" /><LoadingState label="Loading decision provenance" /></div>;
  if (error) return <div className="system-page"><IntelligenceTitle title="Decision Engine" /><ErrorState message={error} onRetry={load} /></div>;

  return <div className="system-page">
    <IntelligenceTitle title="Decision Engine" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh decision engine"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More decision engine actions"><span className="more-dots">•••</span></button></>} />
    <div className="engine-banner"><div><span className="engine-mark"><ShieldIcon size={18} /></span><div><strong>Deterministic recovery engine</strong><span>Decision authority for stored recovery cases</span></div></div><StatusBadge status="AUTHORITATIVE" /></div>
    <section className="engine-metrics"><EngineMetric label="Stored decisions" value={String(decisions.length)} note="Persisted decision records" /><EngineMetric label="Latest action" value={latest ? formatAction(latest.selected_action) : "—"} note={latest ? `Recorded ${formatDate(latest.created_at)}` : "No stored decision"} /><EngineMetric label="Predicted recovery" value={latest ? formatPercent(latest.predicted_probability) : "—"} note="Latest stored prediction" /><EngineMetric label="Expected net" value={latest ? formatPaise(latest.expected_net_value_paise) : "—"} note="Latest stored economics" /></section>
    {!latest ? <IntelEmpty label="No stored decisions are available yet. Decision provenance will appear after a recovery case is evaluated." /> : <>
      <IntelligencePanel title="Decision provenance" note="Latest stored trace"><div className="provenance-grid">{versions.map(([label, value]) => <div className="provenance-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="provenance-case"><span>Latest decision</span><Link href={`/cases/${latest.recovery_case_id}`}>{latest.recovery_case_id}<ArrowRightIcon size={14} /></Link></div></IntelligencePanel>
      <div className="system-two-column"><IntelligencePanel title="How the engine selects" note="Stored behavior"><div className="engine-rule-list"><EngineRule text="Scores observable recovery context." /><EngineRule text="Applies action cost and fatigue treatment." /><EngineRule text="Removes candidates blocked by policy constraints." /><EngineRule text="Persists the selected permissible expected-net action." /></div></IntelligencePanel><IntelligencePanel title="Latest selection" note="Read-only case link"><div className="selection-readout"><span>Selected action</span><strong>{formatAction(latest.selected_action)}</strong><div className="selection-bar"><i style={{ width: `${Math.max(4, Math.min(100, latest.predicted_probability * 100))}%` }} /></div><small>{formatPercent(latest.predicted_probability)} predicted recovery · {formatPaise(latest.expected_net_value_paise)} expected net</small></div><Link className="engine-link" href={`/cases/${latest.recovery_case_id}`}>Open Decision Room <ArrowRightIcon size={14} /></Link></IntelligencePanel></div>
    </>}
    <div className="system-footnote"><CheckIcon size={15} /><span>LLM assistance is not required for financial decisioning. Explanations remain optional and non-authoritative.</span></div>
  </div>;
}

function EngineMetric({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="engine-metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

function EngineRule({ text }: { text: string }) {
  return <div className="engine-rule"><CheckIcon size={15} /><span>{text}</span></div>;
}

function traceValue(decision: Decision, key: string) {
  const value = decision.trace_json[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : "Not exposed";
}
