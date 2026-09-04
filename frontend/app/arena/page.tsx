"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRightIcon, CheckIcon, RefreshIcon, ShieldIcon } from "../../components/icons";
import { Button, DropdownField, ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle } from "../../components/intelligence-workspace";
import { api, ApiError } from "../../lib/api";
import { formatPaise, formatPercent } from "../../lib/formatters";
import type { ArenaResponse, ArenaStrategySummary } from "../../lib/types";

const sampleOptions = [
  { value: "25", label: "25 events per policy", tone: "neutral" as const },
  { value: "100", label: "100 events per policy", tone: "blue" as const },
  { value: "250", label: "250 events per policy", tone: "mint" as const },
];

function findBest(rows: ArenaStrategySummary[]) {
  return rows.reduce<ArenaStrategySummary | null>((best, row) => !best || row.net_value_paise > best.net_value_paise ? row : best, null);
}

export default function PolicyLab() {
  const [report, setReport] = useState<ArenaResponse | null>(null);
  const [sampleSize, setSampleSize] = useState("25");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRunAt, setLastRunAt] = useState<string | null>(null);

  const run = async (requestedSampleSize = Number(sampleSize)) => {
    setLoading(true);
    setError(null);
    try {
      const nextReport = await api.runArena({ count_per_seed: requestedSampleSize });
      setReport(nextReport);
      setLastRunAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Policy experiment could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void run(25); }, []);

  const bestRow = useMemo(() => report ? findBest(report.rows) : null, [report]);
  const chimeraRow = useMemo(() => report?.rows.find((row) => row.policy_name === "CHIMERA") ?? null, [report]);
  const focusRow = chimeraRow ?? bestRow;
  const chimeraIsBest = Boolean(chimeraRow && bestRow && chimeraRow.policy_name === bestRow.policy_name);

  return <div className="evaluation-page">
    <IntelligenceTitle title="Policy Lab" action={<div className="workspace-actions"><Button kind="primary" onClick={() => void run()} disabled={loading}>{loading ? "Running" : "Run experiment"}</Button><button className="square-control" type="button" onClick={() => void run()} disabled={loading} aria-label="Refresh policy experiment"><RefreshIcon size={16} /></button></div>} />
    <div className="workspace-meta standalone-meta"><span>Environment: Evaluation</span><span>Data: Synthetic</span><span>Decision authority: backend policies</span>{lastRunAt && <span>Last run: {new Date(lastRunAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}</div>

    <section className="evaluation-banner"><div><div className="evaluation-banner-icon"><ShieldIcon size={18} /></div><div><strong>Run the same failures through every policy</strong><p>Policy Lab isolates decision quality from customer and provider noise. Each strategy sees the same frozen event batch and is evaluated independently.</p></div></div>{report && <StatusBadge status={report.same_event_batch_across_policies ? "SHARED_BATCH" : "INVALID_BATCH"} />}</section>

    <IntelligencePanel title="Experiment controls" note="Reproducible run"><div className="policy-lab-controls"><div className="policy-lab-control-copy"><strong>Sample size</strong><p>Increase the batch when comparing small differences between policies. The seed stays fixed for comparable runs.</p></div><div className="policy-lab-control-actions"><DropdownField label="Events" value={sampleSize} onChange={setSampleSize} options={sampleOptions} /></div></div></IntelligencePanel>

    {error && <ErrorState message={error} onRetry={() => void run()} />}
    {loading && !report ? <LoadingState label="Running independent policy evaluations" /> : report && <>
      <section className="intelligence-metric-grid" aria-label="Policy Lab summary">
        <IntelligenceMetric label="Best observed policy" value={bestRow?.strategy ?? "—"} note="Highest net value in this batch" tone="mint" />
        <IntelligenceMetric label="CHIMERA recovery" value={chimeraRow ? formatPercent(chimeraRow.recovery_rate) : "—"} note={chimeraRow ? `${chimeraRow.interventions} interventions` : "Policy result unavailable"} />
        <IntelligenceMetric label="Recovered value" value={focusRow ? formatPaise(focusRow.recovered_revenue_paise) : "—"} note={focusRow ? `${focusRow.strategy} observed result` : "No result"} tone="amber" />
        <IntelligenceMetric label="Guardrail violations" value={String(report.rows.reduce((total, row) => total + row.policy_violations, 0))} note="Across all policy runs" tone={report.rows.some((row) => row.policy_violations > 0) ? "red" : "default"} />
      </section>

      <div className="arena-result-grid">
        <IntelligencePanel title="Policy comparison" note="Same batch, independent runs"><div className="arena-table-wrap"><table className="arena-table policy-lab-table"><thead><tr><th>Policy</th><th>Recovery rate</th><th>Recovered value</th><th>Net value</th><th>Interventions</th><th>Violations</th></tr></thead><tbody>{report.rows.map((row) => <tr key={row.policy_name}><th scope="row"><span className={`arena-strategy-dot ${row.policy_name.toLowerCase()}`} />{row.strategy}{row.policy_name === bestRow?.policy_name && <span className="policy-lab-best">Best</span>}</th><td>{formatPercent(row.recovery_rate)}</td><td>{formatPaise(row.recovered_revenue_paise)}</td><td className={row.net_value_paise >= 0 ? "value-positive" : "value-negative"}>{formatPaise(row.net_value_paise)}</td><td>{row.interventions}</td><td className={row.policy_violations > 0 ? "value-negative" : ""}>{row.policy_violations}</td></tr>)}</tbody></table></div></IntelligencePanel>
        <IntelligencePanel title="What the run says" note="Operator readout"><div className="policy-lab-verdict">{focusRow ? <><div className="policy-lab-verdict-head"><span className={`arena-strategy-dot ${focusRow.policy_name.toLowerCase()}`} /><strong>{chimeraIsBest ? "CHIMERA leads this batch" : `${bestRow?.strategy ?? "A policy"} leads this batch`}</strong><StatusBadge status={chimeraIsBest ? "BEST_OBSERVED" : "COMPARE"} /></div><p>{chimeraIsBest ? "The policy produced the highest net recovery value under the current simulator assumptions." : "CHIMERA is included in the comparison, but another policy produced the highest net recovery value in this run."}</p><div className="policy-lab-verdict-meta"><div><span>Net value</span><b>{formatPaise(focusRow.net_value_paise)}</b></div><div><span>Recovery rate</span><b>{formatPercent(focusRow.recovery_rate)}</b></div></div></> : <p>No policy result is available yet.</p>}</div><div className="policy-lab-caution"><ShieldIcon size={14} /><span>Use this to compare policy behavior. It is not a production recovery-rate claim.</span></div></IntelligencePanel>
      </div>

      <IntelligencePanel title="Batch integrity" note="Read before acting"><div className="integrity-grid"><div><CheckIcon size={15} /><span>Same event batch across strategies</span></div><div><CheckIcon size={15} /><span>{report.batch.total_events} total events · {report.batch.count_per_seed} per seed</span></div><div><CheckIcon size={15} /><span>Seed recorded: {report.batch.seeds.join(", ")}</span></div><div><CheckIcon size={15} /><span>Simulator {report.simulator_version} · config {report.config_hash.slice(0, 12)}</span></div><div className="policy-lab-integrity-wide"><ArrowRightIcon size={15} /><span>{report.methodology}</span></div></div></IntelligencePanel>
    </>}
  </div>;
}
