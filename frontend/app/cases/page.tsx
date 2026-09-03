"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "../../lib/api";
import type { RecoveryCase } from "../../lib/types";
import { formatAction, formatFailureReason, formatPaise } from "../../lib/formatters";
import { isActiveRecovery, isRecovered, isUnresolved } from "../../lib/operations";
import { ArrowRightIcon, RefreshIcon } from "../../components/icons";
import { DropdownField, ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { CaseTable } from "../../components/case-table";

type CaseFilter = "all" | "active" | "ready" | "recovered" | "escalated" | "unresolved";

export default function CasesPage() {
  return <Suspense fallback={<div className="operations-page"><LoadingState label="Loading recovery operations" /></div>}><CasesContent /></Suspense>;
}

function CasesContent() {
  const searchParams = useSearchParams();
  const actionQueue = searchParams.get("status") === "DECIDED";
  const requestedFailure = searchParams.get("failure_reason") ?? "";
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [filter, setFilter] = useState<CaseFilter>(actionQueue ? "ready" : "all");
  const [failureReason, setFailureReason] = useState(requestedFailure);
  const [intervention, setIntervention] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const response = await api.listCases({ page: 1, pageSize: 100 });
      setCases(response.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load recovery cases.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { setFilter(actionQueue ? "ready" : "all"); }, [actionQueue]);
  useEffect(() => { setFailureReason(requestedFailure); }, [requestedFailure]);
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(true), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const failureOptions = useMemo(() => Array.from(new Set(cases.map((item) => item.failure_reason))).sort(), [cases]);
  const actionOptions = useMemo(() => Array.from(new Set(cases.map((item) => item.latest_decision?.selected_action).filter((item): item is string => Boolean(item)))).sort(), [cases]);
  const effectiveFilter = actionQueue ? "ready" : filter;
  const visibleCases = useMemo(() => cases.filter((item) => {
    const ready = item.status === "DECIDED" || item.status === "ACTION_PENDING";
    const statusMatch = effectiveFilter === "all" || effectiveFilter === "active" && isActiveRecovery(item) || effectiveFilter === "ready" && ready || effectiveFilter === "recovered" && isRecovered(item) || effectiveFilter === "unresolved" && isUnresolved(item) || effectiveFilter === "escalated" && (item.status === "UNRECOVERED" || item.latest_decision?.selected_action === "ESCALATE");
    return statusMatch && (!failureReason || item.failure_reason === failureReason) && (!intervention || item.latest_decision?.selected_action === intervention);
  }), [cases, effectiveFilter, failureReason, intervention]);

  const summary = useMemo(() => ({
    total: cases.length,
    active: cases.filter(isActiveRecovery).length,
    atRisk: cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED").reduce((sum, item) => sum + item.amount_paise, 0),
    unresolved: cases.filter((item) => item.status === "UNRECOVERED").reduce((sum, item) => sum + item.amount_paise, 0),
    ready: cases.filter((item) => item.status === "DECIDED" || item.status === "ACTION_PENDING").length,
  }), [cases]);

  return <div className="operations-page">
    <div className="workspace-titlebar">
      <div><h1>{actionQueue ? "Action Queue" : "Case Queue"}</h1></div>
      <div className="workspace-actions"><button className="square-control" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh cases"><RefreshIcon size={16} /></button></div>
    </div>

    <section className="queue-summary-strip" aria-label="Recovery queue summary">
      <QueueMetric label="Cases in View" value={String(visibleCases.length)} />
      <QueueMetric label="Active Recovery" value={String(summary.active)} />
      <QueueMetric label="Value at Risk" value={formatPaise(summary.atRisk)} tone="amber" />
      <QueueMetric label="Unresolved Value" value={formatPaise(summary.unresolved)} tone="red" />
    </section>

    <section className="queue-workspace">
      <div className="queue-toolbar">
        <div><strong>{visibleCases.length} {visibleCases.length === 1 ? "Case" : "Cases"}</strong></div>
        <div className="queue-filters" aria-label="Recovery case filters">
          <QueueFilter label="View" value={effectiveFilter} onChange={(value) => setFilter(value as CaseFilter)} options={actionQueue ? [{ value: "ready", label: "Ready for Action", tone: "blue" }, { value: "all", label: "All Queued Cases" }, { value: "active", label: "All Active Recovery", tone: "mint" }] : [{ value: "all", label: "All Cases" }, { value: "active", label: "Active Recovery", tone: "mint" }, { value: "recovered", label: "Recovered", tone: "mint" }, { value: "escalated", label: "Escalated", tone: "amber" }, { value: "unresolved", label: "Unresolved", tone: "red" }]} />
          <QueueFilter label="Failure" value={failureReason} onChange={setFailureReason} options={[{ value: "", label: "All Failure Patterns" }, ...failureOptions.map((value) => ({ value, label: formatFailureReason(value), tone: "red" as const }))]} />
          <QueueFilter label="Action" value={intervention} onChange={setIntervention} options={[{ value: "", label: "All Actions" }, ...actionOptions.map((value) => ({ value, label: formatAction(value), tone: actionTone(value) }))]} />
        </div>
      </div>
      {error ? <ErrorState message={error} onRetry={load} /> : loading ? <QueueSkeleton /> : <CaseTable cases={visibleCases} queueMode={actionQueue} />}
    </section>

    <div className="queue-footnote"><StatusBadge status="READ_ONLY" /><span>Execution remains controlled by backend eligibility and explicit confirmation in Decision Room.</span><a href="/methodology">View guardrails <ArrowRightIcon size={14} /></a></div>
  </div>;
}

function QueueMetric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "amber" | "red" }) {
  return <div className={`queue-metric ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

function QueueFilter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string; tone?: "neutral" | "blue" | "mint" | "amber" | "red" | "violet" }[] }) {
  return <DropdownField className="queue-filter" label={label} value={value} onChange={onChange} options={options} />;
}

function actionTone(action: string): "neutral" | "blue" | "mint" | "amber" | "red" | "violet" {
  if (action === "PAYMENT_LINK") return "blue";
  if (action === "VOICE_RECOVERY") return "violet";
  if (action === "RETRY_LATER") return "amber";
  if (action === "ESCALATE") return "red";
  if (action === "SEND_MESSAGE") return "mint";
  return "neutral";
}

function QueueSkeleton() {
  return <div className="queue-skeleton" aria-label="Loading cases"><span /><span /><span /><span /><span /></div>;
}
