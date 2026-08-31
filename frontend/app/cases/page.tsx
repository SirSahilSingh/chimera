"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "../../lib/api";
import type { RecoveryCase } from "../../lib/types";
import { formatAction, formatFailureReason, formatPaise } from "../../lib/formatters";
import { isActiveRecovery, isRecovered, isUnresolved } from "../../lib/operations";
import { ArrowRightIcon, ChevronDownIcon, RefreshIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
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
  const visibleCases = useMemo(() => cases.filter((item) => {
    const ready = item.status === "DECIDED" || item.status === "ACTION_PENDING";
    const statusMatch = filter === "all" || filter === "active" && isActiveRecovery(item) || filter === "ready" && ready || filter === "recovered" && isRecovered(item) || filter === "unresolved" && isUnresolved(item) || filter === "escalated" && (item.status === "UNRECOVERED" || item.latest_decision?.selected_action === "ESCALATE");
    return statusMatch && (!failureReason || item.failure_reason === failureReason) && (!intervention || item.latest_decision?.selected_action === intervention);
  }), [cases, filter, failureReason, intervention]);

  const summary = useMemo(() => ({
    total: cases.length,
    active: cases.filter(isActiveRecovery).length,
    atRisk: cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED").reduce((sum, item) => sum + item.amount_paise, 0),
    unresolved: cases.filter((item) => item.status === "UNRECOVERED").reduce((sum, item) => sum + item.amount_paise, 0),
    ready: cases.filter((item) => item.status === "DECIDED" || item.status === "ACTION_PENDING").length,
  }), [cases]);

  return <div className="operations-page">
    <div className="workspace-titlebar">
      <div><h1>{actionQueue ? "Action Queue" : "Case Queue"}</h1><div className="workspace-meta"><span>Data: synthetic stored records</span><span>{cases.length} cases</span><span>Read-only queue</span></div></div>
      <div className="workspace-actions"><button className="square-control" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh cases"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More case queue actions"><span className="more-dots">•••</span></button></div>
    </div>

    <section className="queue-summary-strip" aria-label="Recovery queue summary">
      <QueueMetric label="Cases in view" value={String(visibleCases.length)} note={actionQueue ? "Ready for action" : `${summary.total} stored`} />
      <QueueMetric label="Active recovery" value={String(summary.active)} note={`${summary.ready} ready to execute`} />
      <QueueMetric label="Value at risk" value={formatPaise(summary.atRisk)} note="Open recovery exposure" tone="amber" />
      <QueueMetric label="Unresolved value" value={formatPaise(summary.unresolved)} note="Recorded unresolved" tone="red" />
    </section>

    <section className="queue-workspace">
      <div className="queue-toolbar">
        <div><strong>{visibleCases.length} {visibleCases.length === 1 ? "case" : "cases"}</strong><span>Every row links to its Decision Room.</span></div>
        <div className="queue-filters" aria-label="Recovery case filters">
          <QueueFilter label="View" value={filter} onChange={(value) => setFilter(value as CaseFilter)} options={actionQueue ? [{ value: "ready", label: "Ready for action" }, { value: "all", label: "All queued cases" }, { value: "active", label: "All active recovery" }] : [{ value: "all", label: "All cases" }, { value: "active", label: "Active recovery" }, { value: "recovered", label: "Recovered" }, { value: "escalated", label: "Escalated" }, { value: "unresolved", label: "Unresolved" }]} />
          <QueueFilter label="Failure" value={failureReason} onChange={setFailureReason} options={[{ value: "", label: "All failure patterns" }, ...failureOptions.map((value) => ({ value, label: formatFailureReason(value) }))]} />
          <QueueFilter label="Action" value={intervention} onChange={setIntervention} options={[{ value: "", label: "All actions" }, ...actionOptions.map((value) => ({ value, label: formatAction(value) }))]} />
        </div>
      </div>
      {error ? <ErrorState message={error} onRetry={load} /> : loading ? <QueueSkeleton /> : <CaseTable cases={visibleCases} queueMode={actionQueue} />}
    </section>

    <div className="queue-footnote"><StatusBadge status="READ_ONLY" /><span>Execution remains controlled by backend eligibility and explicit confirmation in Decision Room.</span><a href="/methodology">View guardrails <ArrowRightIcon size={14} /></a></div>
  </div>;
}

function QueueMetric({ label, value, note, tone = "default" }: { label: string; value: string; note: string; tone?: "default" | "amber" | "red" }) {
  return <div className={`queue-metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

function QueueFilter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[] }) {
  return <label className="queue-filter"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><ChevronDownIcon size={13} /></label>;
}

function QueueSkeleton() {
  return <div className="queue-skeleton" aria-label="Loading cases"><span /><span /><span /><span /><span /></div>;
}
