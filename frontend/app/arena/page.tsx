"use client";

import { useEffect, useState } from "react";
import { ArrowRightIcon, CheckIcon, RefreshIcon, ShieldIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle } from "../../components/intelligence-workspace";
import { api, ApiError } from "../../lib/api";
import { formatPaise, formatPercent } from "../../lib/formatters";
import type { ArenaResponse } from "../../lib/types";

export default function RecoveryArena() {
  const [report, setReport] = useState<ArenaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try { setReport(await api.runArena({ count_per_seed: 25 })); }
    catch (err) { setError(err instanceof ApiError ? err.detail : "Arena comparison could not be loaded."); }
    finally { setLoading(false); }
  };

  useEffect(() => { void run(); }, []);

  return <div className="evaluation-page">
    <IntelligenceTitle title="Recovery Arena" action={<button className="square-control" type="button" onClick={run} disabled={loading} aria-label="Run arena comparison"><RefreshIcon size={16} /></button>} />
    <div className="workspace-meta standalone-meta"><span>Environment: Evaluation</span><span>Data: Synthetic</span><span>Same event batch across strategies</span></div>
    {error && <ErrorState message={error} onRetry={run} />}
    {loading && !report ? <LoadingState label="Running independent strategy evaluations" /> : report && <>
      <section className="evaluation-banner"><div><div className="evaluation-banner-icon"><ShieldIcon size={18} /></div><div><strong>{report.batch.label}</strong><p>Every strategy is evaluated against the same frozen event batch. This is comparative evidence, not a production performance claim.</p></div></div><StatusBadge status={report.same_event_batch_across_policies ? "SHARED_BATCH" : "INVALID_BATCH"} /></section>
      <section className="intelligence-metric-grid" aria-label="Arena summary"><IntelligenceMetric label="Events" value={String(report.batch.total_events)} note={`${report.batch.count_per_seed} events per seed`} /><IntelligenceMetric label="Value at risk" value={formatPaise(report.batch.value_at_risk_paise)} note="Synthetic batch exposure" tone="amber" /><IntelligenceMetric label="Simulator" value={report.simulator_version} note="Frozen evaluation version" /><IntelligenceMetric label="Config hash" value={report.config_hash.slice(0, 12)} note="Reproducibility reference" /></section>
      <div className="arena-result-grid"><IntelligencePanel title="Strategy comparison" note="Independent policy runs"><div className="arena-table-wrap"><table className="arena-table"><thead><tr><th>Strategy</th><th>Recovered revenue</th><th>Net value</th><th>Interventions</th><th>Violations</th></tr></thead><tbody>{report.rows.map((row) => <tr key={row.policy_name}><th scope="row"><span className={`arena-strategy-dot ${row.policy_name.toLowerCase()}`} />{row.strategy}</th><td>{formatPaise(row.recovered_revenue_paise)}</td><td className={row.net_value_paise >= 0 ? "value-positive" : "value-negative"}>{formatPaise(row.net_value_paise)}</td><td>{row.interventions}</td><td>{row.policy_violations}</td></tr>)}</tbody></table></div></IntelligencePanel><IntelligencePanel title="Recovered revenue" note="Observed recovery rate"><div className="arena-bars">{report.rows.map((row) => <div className="arena-bar-row" key={row.policy_name}><div><span>{row.strategy}</span><b>{formatPaise(row.recovered_revenue_paise)}</b></div><div className="arena-bar-track"><span style={{ width: `${row.bar_percent}%` }} /></div><small>{formatPercent(row.recovery_rate)} observed recovery rate</small></div>)}</div></IntelligencePanel></div>
      <IntelligencePanel title="Batch integrity" note="Read before interpreting"><div className="integrity-grid"><div><CheckIcon size={15} /><span>Same event batch across strategies</span></div><div><CheckIcon size={15} /><span>Reproducible development seed: {report.batch.seeds.join(", ")}</span></div><div><CheckIcon size={15} /><span>Configuration hash recorded</span></div><div><ArrowRightIcon size={15} /><span>Results compare policy behavior only; they do not predict real-world recovery.</span></div></div></IntelligencePanel>
    </>}
  </div>;
}
