"use client";

import { useEffect, useState } from "react";
import { AlertIcon, ArrowRightIcon, CheckIcon, ClockIcon } from "../../components/icons";
import { ErrorState, LoadingState, PageHeader, StatusBadge } from "../../components/shell";
import { api, ApiError } from "../../lib/api";
import { formatAction, formatFailureReason, formatPaise, formatPercent } from "../../lib/formatters";
import type { LearningDrift, LearningFunnel, LearningOverview, LearningProvider } from "../../lib/types";

export default function LearningPage() {
  const [overview, setOverview] = useState<LearningOverview | null>(null);
  const [funnel, setFunnel] = useState<LearningFunnel>([]);
  const [providers, setProviders] = useState<LearningProvider[]>([]);
  const [drift, setDrift] = useState<LearningDrift | null>(null);
  const [mode, setMode] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const [summary, funnelResponse, providerResponse, driftResponse] = await Promise.all([api.learningOverview(mode || undefined), api.learningFunnel(mode || undefined), api.learningProviders(mode || undefined), api.learningDrift(mode || undefined)]);
      setOverview(summary); setFunnel(funnelResponse.funnel.stages); setProviders(providerResponse.providers); setDrift(driftResponse);
    } catch (err) { setError(err instanceof ApiError ? err.detail : "Could not load outcome learning."); } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, [mode]);

  if (loading) return <div className="learning-page"><PageHeader eyebrow="Learn" title="Learn from outcomes" description="Observe what happened across persisted recovery journeys." /><LoadingState label="Loading outcome intelligence" /></div>;
  if (error) return <div className="learning-page"><PageHeader eyebrow="Learn" title="Learn from outcomes" description="Observe what happened across persisted recovery journeys." /><ErrorState message={error} onRetry={load} /></div>;
  if (!overview) return null;
  const overall = overview.overall;
  return <div className="learning-page">
    <PageHeader eyebrow="Learn" title="Learn from outcomes" description="POST-DEPLOYMENT OBSERVATIONAL ANALYSIS from persisted CHIMERA records. This view never retrains the model or changes a decision." action={<label className="learning-filter"><span>Provider mode</span><select value={mode} onChange={(event) => setMode(event.target.value)}><option value="">All modes</option>{overview.provider_modes.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>} />
    <div className="learning-warning"><AlertIcon size={17} /><strong>{overview.data_warning ?? "No non-production warning"}</strong><span>Findings are observational and sample-size dependent.</span></div>
    <section className="learning-kpis"><Metric label="Cases observed" value={String(overall.total_cases)} note={`${overall.completed_cases} completed · ${overall.pending_cases} pending`} /><Metric label="Observed recovery" value={overall.recovery_rate === null ? "—" : formatPercent(overall.recovery_rate)} note={`${overall.recovered_cases} recovered`} tone="mint" /><Metric label="Gross recovered" value={formatPaise(overall.gross_recovered_amount_paise)} note="Persisted recovered amounts" tone="mint" /><Metric label="Net recovered" value={formatPaise(overall.net_recovered_amount_paise)} note="After stored action economics" tone="blue" /></section>
    <div className="learning-grid"><section className="learning-panel"><PanelTitle title="Action performance" note="All seven actions · observational" /><div className="learning-table"><div className="learning-row header"><span>Action</span><span>Selected</span><span>Recovery</span><span>Reliability</span></div>{overview.actions.map((row) => <div className="learning-row" key={row.action}><strong>{formatAction(row.action)}</strong><span>{row.selection_count}</span><span>{row.recovery_rate === null ? "—" : formatPercent(row.recovery_rate)}</span><StatusBadge status={row.reliability} /></div>)}</div></section>
      <section className="learning-panel"><PanelTitle title="Failure reason performance" note="Stored case groups" /><div className="learning-table">{overview.failures.length ? overview.failures.map((row) => <div className="learning-row failure-row" key={row.failure_reason}><div><strong>{formatFailureReason(row.failure_reason)}</strong><small>{row.case_count} cases · {row.completed_count} completed</small></div><span>{row.recovery_rate === null ? "—" : formatPercent(row.recovery_rate)}</span><span>{row.best_action ? formatAction(row.best_action) : "—"}</span></div>) : <Empty label="No persisted outcomes yet." />}</div></section></div>
    <div className="learning-grid"><section className="learning-panel"><PanelTitle title="Recovery funnel" note="NOT_APPLICABLE stages are excluded" /><div className="learning-funnel">{funnel.map((row) => <div className="funnel-row" key={row.stage}><span>{row.stage.replaceAll("_", " ")}</span><b>{row.completed}/{row.entered}</b><small>{row.status === "NOT_APPLICABLE" ? "Not applicable" : row.drop_off_rate === null ? "—" : `${formatPercent(row.drop_off_rate)} drop-off`}</small></div>)}</div></section>
      <section className="learning-panel"><PanelTitle title="Provider performance" note="Modes remain separate" /><div className="learning-table">{providers.length ? providers.map((row) => <div className="provider-learning-row" key={`${row.provider}-${row.provider_mode}`}><div><strong>{row.provider}</strong><small>{row.provider_mode} · {row.reliability}</small></div><span>{row.attempt_count} attempts</span><span>{row.final_recovery_count} recovered</span></div>) : <Empty label="No provider records yet." />}</div></section></div>
    <div className="learning-grid"><section className="learning-panel"><PanelTitle title="Predicted vs observed" note="Selected action only" /><div className="calibration-readout"><div><span>Average predicted</span><strong>{overview.calibration.average_predicted === null ? "—" : formatPercent(overview.calibration.average_predicted)}</strong></div><ArrowRightIcon size={16} /><div><span>Observed recovery</span><strong>{overview.calibration.observed_recovery_rate === null ? "—" : formatPercent(overview.calibration.observed_recovery_rate)}</strong></div><div><span>Brier score</span><strong>{overview.calibration.brier_score === null ? "—" : overview.calibration.brier_score.toFixed(3)}</strong></div></div><p className="learning-note">{overview.calibration.sample_size ? `${overview.calibration.sample_size} completed cases in the observational comparison.` : "No completed cases with stored predictions are available."}</p></section>
      <section className="learning-panel"><PanelTitle title="Observable drift" note="Configurable recent vs baseline windows" />{drift?.status === "INSUFFICIENT_DATA" ? <Empty label="Insufficient persisted cases for drift detection." /> : <div className="drift-list">{drift?.metrics.map((row) => <div className="drift-row" key={row.metric}><span>{row.metric.replaceAll("_", " ")}</span><strong>{row.drift_score.toFixed(3)}</strong><StatusBadge status={row.severity} /></div>)}</div>}</section></div>
    <div className="learning-grid"><section className="learning-panel"><PanelTitle title="Operational insights" note="Deterministic rules with evidence" />{overview.insights.length ? <div className="insight-stack">{overview.insights.slice(0, 8).map((item, index) => <div className="learning-insight" key={`${item.title}-${index}`}><CheckIcon size={15} /><div><strong>{item.title}</strong><p>{item.evidence} · {item.reliability}</p><small>{item.limitation}</small></div></div>)}</div> : <Empty label="No evidence-backed insights yet." />}</section><section className="learning-panel"><PanelTitle title="Recommendations" note="Human review required" />{overview.recommendations.length ? <div className="insight-stack">{overview.recommendations.slice(0, 8).map((item, index) => <div className="learning-insight recommendation" key={`${item.recommendation}-${index}`}><ClockIcon size={15} /><div><strong>{item.recommendation}</strong><p>{item.evidence}</p><small>{item.review_requirement}</small></div></div>)}</div> : <Empty label="No recommendations yet." />}</section></div>
  </div>;
}

function Metric({ label, value, note, tone = "" }: { label: string; value: string; note: string; tone?: string }) { return <div className={`learning-metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>; }
function PanelTitle({ title, note }: { title: string; note: string }) { return <div className="panel-heading"><div><h2>{title}</h2></div><span className="panel-note">{note}</span></div>; }
function Empty({ label }: { label: string }) { return <div className="learning-empty">{label}</div>; }
