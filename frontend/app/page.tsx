"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertIcon, ArrowRightIcon, ChevronDownIcon, RefreshIcon } from "../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../components/shell";
import { api, ApiError } from "../lib/api";
import { caseDisplayId, isActiveRecovery, isRecovered, isUnresolved, statusLabel } from "../lib/operations";
import { formatAction, formatDate, formatFailureReason, formatPaise, formatPercent } from "../lib/formatters";
import type { ProviderReadiness, RecoveryCase } from "../lib/types";

export default function CommandCenter() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [providers, setProviders] = useState<ProviderReadiness[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [response, readiness] = await Promise.all([api.listCases({ page: 1, pageSize: 100 }), api.providerReadiness()]);
      setCases(response.items);
      setTotal(response.total);
      setProviders(readiness);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load the recovery overview.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(true), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const stats = useMemo(() => {
    const unresolved = cases.filter(isUnresolved);
    const recovered = cases.filter(isRecovered);
    const resolved = recovered.length + cases.filter((item) => item.status === "UNRECOVERED").length;
    const attention = cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED");
    const readyProviders = providers.filter((item) => item.readiness_status.endsWith("_VERIFIED") || item.readiness_status === "READY" || item.readiness_status === "CONFIGURED").length;
    const providerIssues = providers.filter((item) => ["FAILED", "UNAVAILABLE", "NOT_CONFIGURED"].includes(item.readiness_status)).length;
    return {
      atRisk: unresolved.reduce((sum, item) => sum + item.amount_paise, 0),
      recoveredValue: recovered.reduce((sum, item) => sum + item.amount_paise, 0),
      active: cases.filter(isActiveRecovery).length,
      attention: attention.length,
      recoveryRate: resolved ? recovered.length / resolved : null,
      readyProviders,
      providerIssues,
    };
  }, [cases, providers]);

  const attentionCases = useMemo(() => cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED").slice(0, 5), [cases]);
  const recentCases = useMemo(() => [...cases].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 7), [cases]);
  const pipeline = [
    { label: "Detected", count: cases.filter((item) => item.status === "NEW").length },
    { label: "Decision ready", count: cases.filter((item) => item.status === "DECIDED").length },
    { label: "Intervening", count: cases.filter((item) => ["ACTION_PENDING", "ACTION_EXECUTED", "PROMISE_TO_PAY_PENDING"].includes(item.status)).length },
    { label: "Recovered", count: cases.filter(isRecovered).length },
  ];

  if (loading) return <div className="overview-page"><LoadingState label="Loading recovery overview" /></div>;
  if (error) return <div className="overview-page"><ErrorState message={error} onRetry={load} /></div>;

  return <div className="overview-page">
    <div className="overview-toolbar"><div className="overview-toolbar-left"><h1>Overview</h1></div><div className="overview-toolbar-actions"><button className="icon-button" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh overview"><RefreshIcon size={16} /></button><Link href="/methodology" className="overview-button overview-button-light">About CHIMERA</Link><button className="icon-button" type="button" aria-label="More overview actions"><span className="more-dots">•••</span></button></div></div>

    <section className="overview-feature">
      <div className="overview-feature-head"><h2>Recovery operations</h2><div className="overview-feature-actions"><StatusBadge status="OPERATIONAL" /><button className="icon-button" type="button" aria-label="More recovery operations"><span className="more-dots">•••</span></button></div></div>
      <div className="overview-feature-body"><div className="overview-feature-copy"><div className="overview-agent-line"><span className="agent-pulse" />CHIMERA Recovery Agent</div><strong>{formatPaise(stats.atRisk)}</strong><span>Value currently at risk</span></div><div className="overview-feature-meta"><span>Decision authority</span><strong>Deterministic engine</strong><span>AI assistance is optional and non-authoritative</span></div></div>
      <div className="overview-feature-footer"><Link href="/cases" className="overview-link">Open recovery operations <ArrowRightIcon size={15} /></Link><span>{total} stored cases · synthetic workspace</span></div>
    </section>

    <section className="overview-stat-grid" aria-label="Recovery summary">
      <SummaryStat label="Recovered case value" value={formatPaise(stats.recoveredValue)} detail={`${cases.filter(isRecovered).length} recovered cases`} tone="success" />
      <SummaryStat label="Active interventions" value={String(stats.active)} detail="Decided or intervening" tone="default" />
      <SummaryStat label="Observed recovery rate" value={stats.recoveryRate === null ? "—" : formatPercent(stats.recoveryRate)} detail="Resolved stored cases" tone="default" />
    </section>

    <section className="overview-grid">
      <div className="overview-panel attention-panel"><div className="overview-panel-head"><h2>Needs attention</h2><Link href="/cases" className="overview-panel-link">View all <ArrowRightIcon size={14} /></Link></div><div className="attention-list">{attentionCases.length ? attentionCases.map((item) => <Link href={`/cases/${item.id}`} className="attention-row" key={item.id}><div className="attention-icon"><AlertIcon size={15} /></div><div className="attention-copy"><strong>{formatFailureReason(item.failure_reason)}</strong><span>{caseDisplayId(item)} · {formatPaise(item.amount_paise, item.currency)}</span></div><div className="attention-action"><strong>{nextAction(item)}</strong><span>{statusLabel(item.status)}</span></div><ArrowRightIcon size={15} /></Link>) : <EmptyLine label="No active cases need attention." />}</div></div>
      <div className="overview-panel posture-panel"><div className="overview-panel-head"><h2>System posture</h2><span className="overview-muted">Current environment</span></div><div className="posture-status"><span className="agent-pulse" /><div><strong>Agent operational</strong><span>Decision engine and API available</span></div></div><div className="posture-line"><span>Providers ready</span><strong>{stats.readyProviders}/{providers.length || "—"}</strong></div><div className="posture-line"><span>Provider issues</span><strong className={stats.providerIssues ? "warning-text" : "success-text"}>{stats.providerIssues || "None"}</strong></div><div className="posture-line"><span>Workspace</span><strong>Demo</strong></div></div>
    </section>

    <section className="overview-panel pipeline-panel"><div className="overview-panel-head"><h2>Recovery pipeline</h2><span className="overview-muted">Current stored state</span></div><div className="pipeline-list">{pipeline.map((stage) => <div className="pipeline-row" key={stage.label}><span>{stage.label}</span><div className="pipeline-track"><i style={{ width: `${Math.min(100, total ? (stage.count / total) * 100 : 0)}%` }} /></div><strong>{stage.count}</strong></div>)}</div></section>

    <section className="overview-panel cases-panel"><div className="overview-panel-head"><h2>Recent cases</h2><div className="cases-panel-actions"><button className="overview-filter" type="button">All cases <ChevronDownIcon size={13} /></button><Link href="/cases" className="overview-panel-link">View all <ArrowRightIcon size={14} /></Link></div></div><div className="overview-case-list">{recentCases.length ? recentCases.map((item) => <Link href={`/cases/${item.id}`} className="overview-case-row" key={item.id}><div className="case-row-main"><strong>{caseDisplayId(item)}</strong><span>{formatFailureReason(item.failure_reason)} · {item.payment_method.toUpperCase()}</span></div><span className="case-row-amount">{formatPaise(item.amount_paise, item.currency)}</span><StatusBadge status={item.status} /><span className="case-row-time">{formatDate(item.updated_at)}</span><ArrowRightIcon size={15} /></Link>) : <EmptyLine label="No stored recovery cases yet." />}</div></section>
  </div>;
}

function SummaryStat({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: "success" | "default" }) {
  return <div className="summary-stat"><span>{label}</span><strong className={tone}>{value}</strong><small>{detail}</small></div>;
}

function nextAction(item: RecoveryCase) {
  if (!item.latest_decision) return "Review decision";
  if (item.status === "DECIDED") return "Execute action";
  if (item.status === "UNRECOVERED") return "Investigate outcome";
  if (item.status === "ACTION_EXECUTED" || item.status === "PROMISE_TO_PAY_PENDING") return "Monitor outcome";
  return formatAction(item.latest_decision.selected_action);
}

function EmptyLine({ label }: { label: string }) {
  return <div className="overview-empty">{label}</div>;
}
