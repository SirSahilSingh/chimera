"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import type { RecoveryCase } from "../../../lib/types";
import { formatAction, formatDate, formatPaise, formatPercent } from "../../../lib/formatters";
import { isRecovered } from "../../../lib/operations";
import { ArrowRightIcon, RefreshIcon } from "../../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../../components/shell";
import { EvidenceBoundary, IntelligenceMetric, IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../../components/intelligence-workspace";

type ActionGroup = { action: string; selected: number; completed: number; recovered: number; gross: number; net: number };

export default function RecoveryPerformancePage() {
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
      setError(err instanceof ApiError ? err.detail : "Could not load recovery outcomes.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const groups = useMemo(() => {
    const map = new Map<string, ActionGroup>();
    cases.forEach((item) => {
      const action = item.latest_decision?.selected_action;
      if (!action) return;
      const current = map.get(action) ?? { action, selected: 0, completed: 0, recovered: 0, gross: 0, net: 0 };
      current.selected += 1;
      if (item.status === "RECOVERED" || item.status === "UNRECOVERED") current.completed += 1;
      if (isRecovered(item)) { current.recovered += 1; current.gross += item.amount_paise; }
      current.net += item.latest_decision?.expected_net_value_paise ?? 0;
      map.set(action, current);
    });
    return Array.from(map.values()).sort((a, b) => b.selected - a.selected);
  }, [cases]);
  const recovered = cases.filter(isRecovered);
  const completed = cases.filter((item) => item.status === "RECOVERED" || item.status === "UNRECOVERED");
  const recoveredValue = recovered.reduce((sum, item) => sum + item.amount_paise, 0);
  const unresolvedValue = cases.filter((item) => item.status === "UNRECOVERED").reduce((sum, item) => sum + item.amount_paise, 0);
  const rate = completed.length ? recovered.length / completed.length : null;
  const funnel = [
    { label: "Detected", count: cases.length },
    { label: "Decision stored", count: cases.filter((item) => Boolean(item.latest_decision)).length },
    { label: "Intervention recorded", count: cases.filter((item) => Boolean(item.latest_execution)).length },
    { label: "Outcome recorded", count: completed.length },
  ];

  if (loading) return <div className="intelligence-page-v2"><IntelligenceTitle title="Recovery Outcomes" /><LoadingState label="Loading observed outcomes" /></div>;
  if (error) return <div className="intelligence-page-v2"><IntelligenceTitle title="Recovery Outcomes" /><ErrorState message={error} onRetry={load} /></div>;

  return <div className="intelligence-page-v2">
    <IntelligenceTitle title="Recovery Outcomes" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh recovery outcomes"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More recovery outcome actions"><span className="more-dots">•••</span></button></>} />
    <EvidenceBoundary sampleSize={cases.length} lastUpdated="On refresh" />
    {!cases.length ? <IntelEmpty label="No observed outcomes yet. Outcomes will appear after stored interventions reach a terminal state." /> : <>
      <section className="intelligence-metric-grid" aria-label="Recovery outcome summary">
        <IntelligenceMetric label="Recovered revenue" value={formatPaise(recoveredValue)} note={`${recovered.length} recovered cases`} tone="mint" />
        <IntelligenceMetric label="Observed recovery rate" value={rate === null ? "—" : formatPercent(rate)} note={`${completed.length} completed cases`} />
        <IntelligenceMetric label="Unresolved value" value={formatPaise(unresolvedValue)} note="Persisted unresolved outcomes" tone="red" />
        <IntelligenceMetric label="Completed cases" value={String(completed.length)} note={`${cases.length - completed.length} still pending`} />
      </section>

      <IntelligencePanel title="Outcome by intervention" note="Stored decisions compared with stored outcomes"><div className="outcome-table"><div className="outcome-table-row outcome-table-header"><span>Action</span><span>Selected</span><span>Completed</span><span>Recovery rate</span><span>Gross value</span><span>Net value</span><span>Reliability</span></div>{groups.length ? groups.map((group) => <div className="outcome-table-row" key={group.action}><strong>{formatAction(group.action)}</strong><span>{group.selected}</span><span>{group.completed}</span><span>{group.completed ? formatPercent(group.recovered / group.completed) : "—"}</span><span className="money-cell">{formatPaise(group.gross)}</span><span className="money-cell">{formatPaise(group.net)}</span><StatusBadge status={reliability(group)} /></div>) : <IntelEmpty label="No stored decisions to compare." />}</div></IntelligencePanel>

      <div className="intelligence-two-column">
        <IntelligencePanel title="Recovery funnel" note="Stored lifecycle states"><div className="outcome-funnel">{funnel.map((stage, index) => <div className="outcome-funnel-row" key={stage.label}><span>{stage.label}</span><div className="intel-bar"><i style={{ width: `${cases.length ? (stage.count / cases.length) * 100 : 0}%` }} /></div><strong>{stage.count}</strong>{index < funnel.length - 1 && <ArrowRightIcon size={14} />}</div>)}</div><div className="intel-boundary-line">A recorded provider action is not a recovered outcome. Only persisted outcome records count as completed.</div></IntelligencePanel>
        <IntelligencePanel title="Recent outcomes" note="Newest stored terminal states"><div className="recent-outcome-list">{completed.slice().sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 6).map((item) => <a href={`/cases/${item.id}`} key={item.id}><div><strong>{item.external_event_id || item.id}</strong><span>{item.status === "RECOVERED" ? "Recovered" : "Unresolved"} · {formatDate(item.updated_at)}</span></div><strong className={item.status === "RECOVERED" ? "mint-text" : "red-text"}>{item.status === "RECOVERED" ? formatPaise(item.amount_paise, item.currency) : "—"}</strong><ArrowRightIcon size={14} /></a>)}{!completed.length && <IntelEmpty label="No terminal outcomes recorded." />}</div></IntelligencePanel>
      </div>

      <IntelligencePanel title="Interpretation boundary" note="Observed, not causal"><div className="boundary-copy"><p>This view reports what happened after stored interventions. It does not prove that an action caused recovery or make a real-world performance claim.</p><p>Net value reflects the stored decision economics available on each case, not a newly calculated recommendation.</p></div></IntelligencePanel>
    </>}
  </div>;
}

function reliability(group: ActionGroup) {
  if (group.selected < 5) return "LIMITED_SAMPLE";
  if (group.completed < group.selected) return "PARTIAL_OBSERVATION";
  return "OBSERVED";
}
