"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRightIcon, ChevronDownIcon, RefreshIcon } from "../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../components/shell";
import { api, ApiError } from "../lib/api";
import { caseDisplayId, isActiveRecovery, isRecovered, isUnresolved } from "../lib/operations";
import { formatAction, formatDate, formatFailureReason, formatPaise, formatPercent } from "../lib/formatters";
import type { ProviderReadiness, RecoveryCase } from "../lib/types";

export default function CommandCenter() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [providers, setProviders] = useState<ProviderReadiness[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attentionOpen, setAttentionOpen] = useState(false);
  const [seenCaseIds, setSeenCaseIds] = useState<string[]>([]);

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

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("chimera-seen-recovery-cases");
      if (stored) setSeenCaseIds(JSON.parse(stored) as string[]);
    } catch {
      setSeenCaseIds([]);
    }
  }, []);

  const stats = useMemo(() => {
    const unresolved = cases.filter(isUnresolved);
    const recovered = cases.filter(isRecovered);
    const resolved = recovered.length + cases.filter((item) => item.status === "UNRECOVERED").length;
    const attention = cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED" && item.latest_decision?.selected_action !== "DO_NOTHING");
    const newCases = cases.filter((item) => item.status === "NEW" && !seenCaseIds.includes(item.id));
    const readyProviders = providers.filter((item) => item.readiness_status.endsWith("_VERIFIED") || item.readiness_status === "READY" || item.readiness_status === "CONFIGURED" || item.readiness_status === "TEST_READY").length;
    const providerIssues = providers.filter((item) => ["FAILED", "UNAVAILABLE", "NOT_CONFIGURED"].includes(item.readiness_status) && item.readiness_status !== "TEST_READY").length;
    return {
      atRisk: unresolved.reduce((sum, item) => sum + item.amount_paise, 0),
      recoveredValue: recovered.reduce((sum, item) => sum + item.amount_paise, 0),
      active: cases.filter(isActiveRecovery).length,
      attention: attention.length,
      newCases: newCases.length,
      recoveryRate: resolved ? recovered.length / resolved : null,
      readyProviders,
      providerIssues,
    };
  }, [cases, providers, seenCaseIds]);

  const attentionCases = useMemo(() => [...cases].filter((item) => !isRecovered(item) && item.status !== "CLOSED" && item.latest_decision?.selected_action !== "DO_NOTHING").sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5), [cases]);
  const recentCases = useMemo(() => [...cases].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 7), [cases]);
  const valueByReason = useMemo(() => {
    const groups = new Map<string, number>();
    cases.forEach((item) => {
      if (isRecovered(item) || item.status === "CLOSED" || item.latest_decision?.selected_action === "DO_NOTHING") return;
      groups.set(item.failure_reason, (groups.get(item.failure_reason) ?? 0) + item.amount_paise);
    });
    return Array.from(groups, ([reason, value]) => ({ reason, value })).sort((a, b) => b.value - a.value).slice(0, 5);
  }, [cases]);
  const pipeline = [
    { label: "Detected (New)", count: cases.filter((item) => item.status === "NEW").length },
    { label: "Decision Ready", count: cases.filter((item) => item.status === "DECIDED").length },
    { label: "Intervening", count: cases.filter((item) => ["ACTION_PENDING", "ACTION_EXECUTED", "PROMISE_TO_PAY_PENDING"].includes(item.status)).length },
    { label: "Recovered", count: cases.filter(isRecovered).length },
  ];

  if (loading) return <div className="overview-page"><LoadingState label="Loading recovery overview" /></div>;
  if (error) return <div className="overview-page"><ErrorState message={error} onRetry={load} /></div>;

  return <div className="overview-page">
    <section className="overview-lead-grid">
      <section className="overview-feature">
        <div className="overview-feature-head"><h2>Recovery Operations</h2><div className="overview-feature-actions"><button className="icon-button" type="button" aria-label="Refresh overview" onClick={() => void load()} disabled={loading}><RefreshIcon size={16} /></button><StatusBadge status="OPERATIONAL" /></div></div>
        <div className="overview-feature-body"><div className="overview-feature-copy"><strong>{formatPaise(stats.atRisk)}</strong><span>Value currently at risk</span></div></div>
        <div className="overview-feature-footer"><Link href="/cases" className="overview-link">Open recovery operations <ArrowRightIcon size={15} /></Link></div>
      </section>

      <div className="overview-panel posture-panel"><div className="overview-panel-head"><h2>System Posture</h2><span className="overview-muted">Current Environment</span></div><div className="posture-status"><span className="agent-pulse" /><div><strong>Agent Operational</strong><span>Decision Engine and API Available</span></div></div><div className="posture-line"><span>Providers Ready</span><strong>{stats.readyProviders}/{providers.length || "—"}</strong></div><div className="posture-line"><span>Provider Issues</span><strong className={stats.providerIssues ? "warning-text" : "success-text"}>{stats.providerIssues || "None"}</strong></div><div className="posture-line"><span>Workspace</span><strong>Demo</strong></div></div>
    </section>

    <section className="overview-stat-grid" aria-label="Recovery summary">
      <SummaryStat label="Recovered case value" value={formatPaise(stats.recoveredValue)} tone="success" />
      <SummaryStat label="Active interventions" value={String(stats.active)} tone="default" />
      <SummaryStat label="Observed recovery rate" value={stats.recoveryRate === null ? "—" : formatPercent(stats.recoveryRate)} tone="default" />
    </section>

    <section className={`overview-panel attention-panel ${attentionOpen ? "open" : ""}`}>
      <button className="overview-panel-head overview-collapse-toggle" type="button" aria-expanded={attentionOpen} onClick={() => { const nextOpen = !attentionOpen; setAttentionOpen(nextOpen); if (nextOpen) { const newlySeen = attentionCases.filter((item) => item.status === "NEW").map((item) => item.id); if (newlySeen.length) { setSeenCaseIds((current) => { const next = Array.from(new Set([...current, ...newlySeen])); window.localStorage.setItem("chimera-seen-recovery-cases", JSON.stringify(next)); return next; }); } } }}><h2>Needs Attention</h2><span className="attention-head-meta">{stats.newCases > 0 && <span className="attention-badge">{stats.newCases} New {stats.newCases === 1 ? "Case" : "Cases"}</span>}<ChevronDownIcon size={15} /></span></button>
      <div className="attention-content"><div className="attention-list">{attentionCases.length ? attentionCases.map((item) => <Link href={`/cases/${item.id}`} className="attention-row" key={item.id}><div className="attention-issue"><i className="attention-dot" /><strong>{formatFailureReason(item.failure_reason)}</strong></div><span className="attention-case-id" title={caseDisplayId(item)}>{compactCaseId(caseDisplayId(item))}</span><span className={`attention-amount ${attentionTone(item)}`}>{formatPaise(item.amount_paise, item.currency)}</span><span className="attention-created">{formatDate(item.created_at)}</span><ArrowRightIcon size={15} /></Link>) : <EmptyLine label="No active cases need attention." />}</div></div>
    </section>

    <section className="overview-analysis-grid">
      <section className="overview-panel pipeline-panel"><div className="overview-panel-head"><h2>Recovery Pipeline</h2><span className="overview-muted">Current Stored State</span></div><div className="pipeline-list">{pipeline.map((stage) => <div className="pipeline-row" key={stage.label}><span>{stage.label}</span><div className="pipeline-track"><i style={{ width: `${Math.min(100, total ? (stage.count / total) * 100 : 0)}%` }} /></div><strong>{stage.count}</strong></div>)}</div></section>
      <section className="overview-panel risk-reason-panel"><div className="overview-panel-head"><h2>Value at Risk by Reason</h2><Link href="/intelligence/failures" className="overview-panel-link">Failure Intelligence <ArrowRightIcon size={14} /></Link></div><div className="risk-reason-list">{valueByReason.length ? valueByReason.map((group) => { const maxValue = valueByReason[0]?.value ?? 0; return <Link href={`/cases?failure_reason=${encodeURIComponent(group.reason)}`} className="risk-reason-row" key={group.reason}><div><strong>{formatFailureReason(group.reason)}</strong><span>{formatPaise(group.value)}</span></div><div className="pipeline-track"><i style={{ width: `${maxValue ? (group.value / maxValue) * 100 : 0}%` }} /></div></Link>; }) : <EmptyLine label="No open value by reason." />}</div></section>
    </section>

    <section className="overview-panel cases-panel"><div className="overview-panel-head"><h2>Recent Cases</h2><Link href="/cases" className="overview-panel-link">View All</Link></div><div className="overview-case-list">{recentCases.length ? recentCases.map((item) => <Link href={`/cases/${item.id}`} className="overview-case-row" key={item.id}><div className="case-row-main"><strong>{formatFailureReason(item.failure_reason)}</strong><span>{caseDisplayId(item)} · {item.payment_method.toUpperCase()}</span></div><span className="case-row-amount">{formatPaise(item.amount_paise, item.currency)}</span><StatusBadge status={item.status} /><span className="case-row-time">{formatDate(item.updated_at)}</span><ArrowRightIcon size={15} /></Link>) : <EmptyLine label="No stored recovery cases yet." />}</div></section>
  </div>;
}

function SummaryStat({ label, value, tone }: { label: string; value: string; tone: "success" | "default" }) {
  return <div className="summary-stat"><span>{label}</span><strong className={tone}>{value}</strong></div>;
}

function nextAction(item: RecoveryCase) {
  if (!item.latest_decision) return "Review decision";
  if (item.status === "DECIDED") return "Execute action";
  if (item.status === "UNRECOVERED") return "Investigate outcome";
  if (item.status === "ACTION_EXECUTED" || item.status === "PROMISE_TO_PAY_PENDING") return "Monitor outcome";
  return formatAction(item.latest_decision.selected_action);
}

function compactCaseId(value: string) {
  return value.length > 25 ? `${value.slice(0, 25)}...` : value;
}

function attentionTone(item: RecoveryCase) {
  const action = item.latest_execution?.action;
  return action === "PAYMENT_LINK" || action === "SEND_MESSAGE" || action === "VOICE_RECOVERY" ? "amber" : "danger";
}

function EmptyLine({ label }: { label: string }) {
  return <div className="overview-empty">{label}</div>;
}
