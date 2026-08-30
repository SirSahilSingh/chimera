"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import type { RecoveryCase } from "../../../lib/types";
import { formatFailureReason, formatPaise, formatPercent } from "../../../lib/formatters";
import { isRecovered } from "../../../lib/operations";
import { AlertIcon, ArrowRightIcon, RefreshIcon } from "../../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../../components/shell";
import { DeepLink, EvidenceBoundary, IntelligenceMetric, IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../../components/intelligence-workspace";

type FailureGroup = { reason: string; count: number; valueAtRisk: number; recovered: number; incident: number };

export default function FailureIntelligencePage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listCases({ page: 1, pageSize: 100 });
      setCases(response.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load failure patterns.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const groups = useMemo(() => {
    const map = new Map<string, FailureGroup>();
    cases.forEach((item) => {
      const current = map.get(item.failure_reason) ?? { reason: item.failure_reason, count: 0, valueAtRisk: 0, recovered: 0, incident: 0 };
      current.count += 1;
      if (!isRecovered(item) && item.status !== "CLOSED") current.valueAtRisk += item.amount_paise;
      if (isRecovered(item)) current.recovered += 1;
      if (item.incident_flag) current.incident += 1;
      map.set(item.failure_reason, current);
    });
    return Array.from(map.values()).sort((a, b) => b.count - a.count || b.valueAtRisk - a.valueAtRisk);
  }, [cases]);
  const openValue = cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED").reduce((sum, item) => sum + item.amount_paise, 0);
  const incidentCases = cases.filter((item) => item.incident_flag);
  const mostCommon = groups[0];

  if (loading) return <div className="intelligence-page-v2"><IntelligenceTitle title="Failure Patterns" /><LoadingState label="Loading failure patterns" /></div>;
  if (error) return <div className="intelligence-page-v2"><IntelligenceTitle title="Failure Patterns" /><ErrorState message={error} onRetry={load} /></div>;

  return <div className="intelligence-page-v2">
    <IntelligenceTitle title="Failure Patterns" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh failure patterns"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More failure pattern actions"><span className="more-dots">•••</span></button></>} />
    <EvidenceBoundary sampleSize={cases.length} lastUpdated="On refresh" />
    {!cases.length ? <IntelEmpty label="No stored failure patterns yet. Payment failures will appear here after the recovery API receives them." /> : <>
      <section className="intelligence-metric-grid" aria-label="Failure pattern summary">
        <IntelligenceMetric label="Revenue exposed" value={formatPaise(openValue)} note="Open recovery exposure" tone="amber" />
        <IntelligenceMetric label="Affected cases" value={String(cases.length)} note="Stored payment failures" />
        <IntelligenceMetric label="Incident signals" value={String(incidentCases.length)} note="Cases with an observable incident flag" tone={incidentCases.length ? "red" : "default"} />
        <IntelligenceMetric label="Most common failure" value={mostCommon ? formatFailureReason(mostCommon.reason) : "—"} note={mostCommon ? `${mostCommon.count} stored cases` : "No pattern yet"} />
      </section>

      <div className="intelligence-two-column">
        <IntelligencePanel title="Failure distribution" note="By stored case count"><div className="pattern-list">{groups.map((group) => <div className="pattern-row" key={group.reason}><div className="pattern-row-head"><strong>{formatFailureReason(group.reason)}</strong><span>{group.count} {group.count === 1 ? "case" : "cases"}</span></div><div className="intel-bar"><i style={{ width: `${(group.count / cases.length) * 100}%` }} /></div><div className="pattern-row-foot"><span>{formatPercent(group.count / cases.length)} of stored cases</span><DeepLink href={`/cases?failure_reason=${encodeURIComponent(group.reason)}`}>View cases</DeepLink></div></div>)}</div></IntelligencePanel>
        <IntelligencePanel title="Value at risk by reason" note="Open cases only"><div className="value-pattern-list">{groups.map((group) => <div className="value-pattern-row" key={group.reason}><div><strong>{formatFailureReason(group.reason)}</strong><span>{group.recovered} recovered of {group.count}</span></div><strong>{formatPaise(group.valueAtRisk)}</strong></div>)}</div><div className="intel-boundary-line">Value is grouped from stored amounts; no causal ranking is inferred.</div></IntelligencePanel>
      </div>

      <div className="intelligence-two-column">
        <IntelligencePanel title="Observable incident signals" note="Stored boolean signals"><div className="incident-readout"><div className="incident-count"><AlertIcon size={17} /><strong>{incidentCases.length}</strong><span>cases marked with an incident signal</span></div><div className="incident-copy">An incident flag is evidence attached to the case at detection time. It is not a root-cause claim.</div></div>{incidentCases.length ? <div className="incident-list">{incidentCases.slice(0, 5).map((item) => <a href={`/cases/${item.id}`} key={item.id}><span>{formatFailureReason(item.failure_reason)}</span><strong>{formatPaise(item.amount_paise, item.currency)}</strong><ArrowRightIcon size={14} /></a>)}</div> : <IntelEmpty label="No incident flags in the current records." />}</IntelligencePanel>
        <IntelligencePanel title="Pattern boundary" note="Read before interpreting"><div className="boundary-copy"><p>Failure Patterns describes where value is exposed in the records CHIMERA has stored.</p><p>It does not estimate hidden demand, claim a provider caused a failure, or predict future recovery.</p><DeepLink href="/methodology">Read methodology and guardrails</DeepLink></div></IntelligencePanel>
      </div>

      <IntelligencePanel title="Cases by pattern" note="Deep-link to the operational queue"><div className="pattern-table"><div className="pattern-table-row pattern-table-header"><span>Failure pattern</span><span>Cases</span><span>Open value</span><span>Signal</span><span /></div>{groups.map((group) => <div className="pattern-table-row" key={group.reason}><strong>{formatFailureReason(group.reason)}</strong><span>{group.count}</span><span>{formatPaise(group.valueAtRisk)}</span><span>{group.incident ? <StatusBadge status="INCIDENT" /> : <span className="muted-text">None stored</span>}</span><DeepLink href={`/cases?failure_reason=${encodeURIComponent(group.reason)}`}>Open queue</DeepLink></div>)}</div></IntelligencePanel>
    </>}
  </div>;
}
