"use client";

import { useEffect, useState } from "react";
import { CheckIcon, ChevronDownIcon, RefreshIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { api, ApiError } from "../../lib/api";
import { formatAction, formatFailureReason, formatPaise, formatPercent } from "../../lib/formatters";
import type { LearningFunnel, LearningOverview, LearningProvider } from "../../lib/types";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../components/intelligence-workspace";

type LearningTab = "overview" | "actions" | "failure-groups" | "funnel" | "providers" | "insights";

const tabs: { id: LearningTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "actions", label: "Actions" },
  { id: "failure-groups", label: "Failure groups" },
  { id: "funnel", label: "Funnel" },
  { id: "providers", label: "Providers" },
  { id: "insights", label: "Insights" },
];

export default function LearningPage() {
  const [overview, setOverview] = useState<LearningOverview | null>(null);
  const [funnel, setFunnel] = useState<LearningFunnel>([]);
  const [providers, setProviders] = useState<LearningProvider[]>([]);
  const [tab, setTab] = useState<LearningTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, funnelResponse, providerResponse] = await Promise.all([api.learningOverview(), api.learningFunnel(), api.learningProviders()]);
      setOverview(summary);
      setFunnel(funnelResponse.funnel.stages);
      setProviders(providerResponse.providers);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load outcome learning.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  if (loading) return <div className="intelligence-page-v2"><IntelligenceTitle title="Outcome Learning" /><LoadingState label="Loading observational learning" /></div>;
  if (error) return <div className="intelligence-page-v2"><IntelligenceTitle title="Outcome Learning" /><ErrorState message={error} onRetry={load} /></div>;
  if (!overview) return <div className="intelligence-page-v2"><IntelligenceTitle title="Outcome Learning" /><IntelEmpty label="No learning summary is available." /></div>;

  const overall = overview.overall;
  return <div className="intelligence-page-v2 learning-workspace">
    <IntelligenceTitle title="Outcome Learning" action={<button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh outcome learning"><RefreshIcon size={16} /></button>} />
    <nav className="learning-tabs" aria-label="Outcome learning views" role="tablist">{tabs.map((item) => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>

    {tab === "overview" && <OverviewTab overview={overview} />}
    {tab === "actions" && <ActionsTab overview={overview} />}
    {tab === "failure-groups" && <FailureGroupsTab overview={overview} />}
    {tab === "funnel" && <FunnelTab funnel={funnel} />}
    {tab === "providers" && <ProvidersTab providers={providers} />}
    {tab === "insights" && <InsightsTab overview={overview} />}
  </div>;
}

function OverviewTab({ overview }: { overview: LearningOverview }) {
  const overall = overview.overall;
  return <div className="learning-tab-content"><section className="intelligence-metric-grid"><IntelligenceMetric label="Cases observed" value={String(overall.total_cases)} note={`${overall.completed_cases} completed · ${overall.pending_cases} pending`} /><IntelligenceMetric label="Observed recovery" value={overall.recovery_rate === null ? "—" : formatPercent(overall.recovery_rate)} note={`${overall.recovered_cases} recovered`} tone="mint" /><IntelligenceMetric label="Gross recovered" value={formatPaise(overall.gross_recovered_amount_paise)} note="Persisted recovered amounts" tone="mint" /><IntelligenceMetric label="Net recovered" value={formatPaise(overall.net_recovered_amount_paise)} note="Stored decision economics" /></section><div className="intelligence-two-column"><IntelligencePanel title="Readout" note={`Analysis ${overview.analysis_version}`}><div className="learning-readout"><div><span>Completed cases</span><strong>{overall.completed_cases}</strong></div><div><span>Unrecovered cases</span><strong>{overall.unrecovered_cases}</strong></div><div><span>Average time to outcome</span><strong>{overall.average_time_to_outcome_seconds === null ? "—" : `${Math.round(overall.average_time_to_outcome_seconds)}s`}</strong></div></div><div className="intel-boundary-line">This workspace describes persisted journeys. It is not an automatic policy or model update.</div></IntelligencePanel><IntelligencePanel title="Evidence-backed insights" note="Open Insights for the full set">{overview.insights.length ? <div className="learning-insight-stack">{overview.insights.slice(0, 3).map((item) => <InsightRow key={item.title} title={item.title} evidence={item.evidence} limitation={item.limitation} />)}</div> : <IntelEmpty label="No evidence-backed insights yet." />}</IntelligencePanel></div></div>;
}

function ActionsTab({ overview }: { overview: LearningOverview }) {
  return <IntelligencePanel title="Action performance" note="Observed selected actions"><div className="learning-data-table"><div className="learning-data-row learning-data-header"><span>Action</span><span>Selected</span><span>Completed</span><span>Recovery rate</span><span>Gross value</span><span>Net value</span><span>Reliability</span></div>{overview.actions.length ? overview.actions.map((row) => <div className="learning-data-row" key={row.action}><strong>{formatAction(row.action)}</strong><span>{row.selection_count}</span><span>{row.completed_count}</span><span>{row.recovery_rate === null ? "—" : formatPercent(row.recovery_rate)}</span><span>{formatPaise(row.gross_recovered_value_paise)}</span><span>{formatPaise(row.net_recovered_value_paise)}</span><StatusBadge status={row.reliability} /></div>) : <IntelEmpty label="No stored action observations." />}</div></IntelligencePanel>;
}

function FailureGroupsTab({ overview }: { overview: LearningOverview }) {
  return <IntelligencePanel title="Failure-group performance" note="Stored case groups"><div className="learning-data-table"><div className="learning-data-row learning-data-header"><span>Failure group</span><span>Cases</span><span>Completed</span><span>Recovery rate</span><span>Best observed action</span><span>Recovered value</span></div>{overview.failures.length ? overview.failures.map((row) => <div className="learning-data-row" key={row.failure_reason}><strong>{formatFailureReason(row.failure_reason)}</strong><span>{row.case_count}</span><span>{row.completed_count}</span><span>{row.recovery_rate === null ? "—" : formatPercent(row.recovery_rate)}</span><span>{row.best_action ? formatAction(row.best_action) : "—"}</span><span>{formatPaise(row.recovered_value_paise)}</span></div>) : <IntelEmpty label="No stored failure groups." />}</div></IntelligencePanel>;
}

function FunnelTab({ funnel }: { funnel: LearningFunnel }) {
  return <IntelligencePanel title="Recovery funnel" note="NOT_APPLICABLE stages are excluded"><div className="learning-funnel-list">{funnel.map((row) => <div className="learning-funnel-row" key={row.stage}><div><strong>{row.stage.replaceAll("_", " ")}</strong><span>{row.status === "NOT_APPLICABLE" ? "Not applicable" : row.drop_off_rate === null ? "No drop-off recorded" : `${formatPercent(row.drop_off_rate)} drop-off`}</span></div><div className="intel-bar"><i style={{ width: `${row.entered ? (row.completed / row.entered) * 100 : 0}%` }} /></div><strong>{row.completed}/{row.entered}</strong></div>)}</div><div className="intel-boundary-line">The funnel shows persisted lifecycle transitions, not an estimate of users who were never observed.</div></IntelligencePanel>;
}

function ProvidersTab({ providers }: { providers: LearningProvider[] }) {
  return <IntelligencePanel title="Provider performance" note="Modes remain separate"><div className="learning-data-table"><div className="learning-data-row learning-data-header"><span>Provider</span><span>Mode</span><span>Attempts</span><span>Requests failed</span><span>Latency</span><span>Recovered</span><span>Reliability</span></div>{providers.length ? providers.map((row) => <div className="learning-data-row" key={`${row.provider}-${row.provider_mode}`}><strong>{row.provider}</strong><span>{row.provider_mode}</span><span>{row.attempt_count}</span><span>{row.failed_requests}</span><span>{row.average_latency_seconds === null ? "—" : `${row.average_latency_seconds.toFixed(2)}s`}</span><span>{row.final_recovery_count}</span><StatusBadge status={row.reliability} /></div>) : <IntelEmpty label="No provider observations." />}</div></IntelligencePanel>;
}

function InsightsTab({ overview }: { overview: LearningOverview }) {
  return <div className="learning-insight-collapsibles"><CollapsibleInsight title="Operational insights" note="Evidence and limitations">{overview.insights.length ? <div className="learning-insight-stack">{overview.insights.map((item, index) => <InsightRow key={`${item.title}-${index}`} title={item.title} evidence={`${item.evidence} · sample size ${item.sample_size}`} limitation={`${item.reliability} · ${item.limitation}`} />)}</div> : <IntelEmpty label="No evidence-backed insights yet." />}</CollapsibleInsight><CollapsibleInsight title="Recommendations" note="Human review required">{overview.recommendations.length ? <div className="learning-insight-stack">{overview.recommendations.map((item, index) => <InsightRow key={`${item.recommendation}-${index}`} title={item.recommendation} evidence={`${item.evidence} · sample size ${item.sample_size}`} limitation={`${item.review_requirement} · ${item.limitation}`} warning />)}</div> : <IntelEmpty label="No human-review recommendations yet." />}</CollapsibleInsight></div>;
}

function CollapsibleInsight({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return <details className="learning-collapsible-panel" open><summary><strong>{title}</strong><span>{note}<ChevronDownIcon size={15} /></span></summary><div>{children}</div></details>;
}

function InsightRow({ title, evidence, warning = false }: { title: string; evidence: string; limitation?: string; warning?: boolean }) {
  const match = title.match(/^([A-Z][A-Z_]+)(\s.*)$/);
  return <article className={`learning-insight-row ${warning ? "warning" : ""}`}><div><strong>{match ? <><span className="insight-action-name">{match[1]}</span>{match[2]}</> : title}</strong><p>{evidence.split(" · sample size")[0]}</p></div></article>;
}
