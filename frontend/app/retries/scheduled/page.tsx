"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRightIcon, CheckIcon, ClockIcon, RefreshIcon, ShieldIcon } from "../../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../../components/shell";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../../components/intelligence-workspace";
import { api, ApiError } from "../../../lib/api";
import { formatDate, shortId } from "../../../lib/formatters";
import type { ScheduledRetry } from "../../../lib/types";

type RetryFilter = "ALL" | "SCHEDULED" | "DUE" | "EXECUTED";

export default function ScheduledRetriesPage() {
  const [retries, setRetries] = useState<ScheduledRetry[]>([]);
  const [filter, setFilter] = useState<RetryFilter>("ALL");
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setRetries(await api.listScheduledRetries());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load scheduled retries.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const now = Date.now();
  const isDue = (item: ScheduledRetry) => item.execution_status === "SCHEDULED" && new Date(item.scheduled_at).getTime() <= now;
  const visible = useMemo(() => retries.filter((item) => filter === "ALL" || filter === "DUE" && isDue(item) || filter === "SCHEDULED" && item.execution_status === "SCHEDULED" || filter === "EXECUTED" && item.execution_status === "EXECUTED"), [retries, filter]);
  const due = retries.filter(isDue).length;
  const scheduled = retries.filter((item) => item.execution_status === "SCHEDULED").length;
  const executed = retries.filter((item) => item.execution_status === "EXECUTED").length;
  const nextRetry = retries.filter((item) => item.execution_status === "SCHEDULED").sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())[0];

  const execute = async (item: ScheduledRetry) => {
    setPendingId(item.id);
    setNotice(null);
    setError(null);
    try {
      const result = await api.executeScheduledRetry(item.id);
      setNotice(`Retry executed for ${shortId(item.recovery_case_id)} · ${result.status.replaceAll("_", " ")}.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The scheduled retry could not be executed.");
    } finally {
      setPendingId(null);
    }
  };

  return <div className="operations-page queue-surface">
    <IntelligenceTitle title="Scheduled Retries" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh scheduled retries"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More scheduled retry actions"><span className="more-dots">•••</span></button></>} />
    <div className="workspace-meta standalone-meta"><span>Data: synthetic stored records</span><span>{retries.length} retry schedules</span><span>Backend eligibility enforced</span></div>

    <section className="intelligence-metric-grid" aria-label="Scheduled retry summary">
      <IntelligenceMetric label="Scheduled" value={String(scheduled)} note="Waiting for their execution window" />
      <IntelligenceMetric label="Due now" value={String(due)} note="Eligible under stored schedule" tone={due ? "amber" : "default"} />
      <IntelligenceMetric label="Executed" value={String(executed)} note="Schedule marked complete" tone={executed ? "mint" : "default"} />
      <IntelligenceMetric label="Next retry" value={nextRetry ? formatDate(nextRetry.scheduled_at) : "—"} note={nextRetry ? "Earliest pending schedule" : "No pending schedule"} />
    </section>

    <IntelligencePanel title="Retry schedule" note={`${visible.length} ${visible.length === 1 ? "record" : "records"}`}>
      <div className="queue-toolbar queue-toolbar-inline">
        <div><strong>Deterministic retry windows</strong><span>Execution is available only when the backend marks a schedule eligible.</span></div>
        <label className="queue-filter"><span>View</span><select value={filter} onChange={(event) => setFilter(event.target.value as RetryFilter)}><option value="ALL">All schedules</option><option value="SCHEDULED">Pending</option><option value="DUE">Due now</option><option value="EXECUTED">Executed</option></select></label>
      </div>
      {error ? <ErrorState message={error} onRetry={load} /> : loading ? <LoadingState label="Loading retry schedule" /> : notice ? <div className="queue-notice"><CheckIcon size={15} /><span>{notice}</span><button type="button" onClick={() => setNotice(null)} aria-label="Dismiss notification">Dismiss</button></div> : null}
      {!loading && !error && <div className="operations-queue-table"><div className="operations-queue-row retry-queue-header"><span>Schedule</span><span>Case</span><span>Reason</span><span>Eligibility</span><span>Execution</span><span>Provider</span><span /></div>{visible.map((item) => <RetryRow item={item} due={isDue(item)} pending={pendingId === item.id} onExecute={() => void execute(item)} key={item.id} />)}</div>}
      {!loading && !error && !visible.length && <IntelEmpty label={filter === "ALL" ? "No scheduled retries are stored yet. A RETRY_LATER decision creates a deterministic schedule here." : "No retry schedules match this view."} />}
    </IntelligencePanel>

    <div className="queue-footnote"><StatusBadge status="READ_ONLY" /><span>Retry timing and eligibility come from the persisted backend schedule; this surface only authorizes an eligible execution.</span><Link href="/system/decision-engine">View decision engine <ArrowRightIcon size={14} /></Link></div>
  </div>;
}

function RetryRow({ item, due, pending, onExecute }: { item: ScheduledRetry; due: boolean; pending: boolean; onExecute: () => void }) {
  const executed = item.execution_status === "EXECUTED";
  return <div className="operations-queue-row retry-queue-row">
    <div className="retry-time-cell"><ClockIcon size={15} /><div><strong>{formatDate(item.scheduled_at)}</strong><span>{item.attempt_number === 1 ? "First attempt" : `Attempt ${item.attempt_number}`}</span></div></div>
    <Link className="queue-case-cell" href={`/cases/${item.recovery_case_id}`}><strong>{shortId(item.recovery_case_id)}</strong><span>{shortId(item.intervention_id)}</span></Link>
    <div className="queue-reason-cell"><strong>{item.schedule_reason.replaceAll("_", " ")}</strong><span>Decision {shortId(item.decision_id)}</span></div>
    <StatusBadge status={item.eligibility_status} />
    <StatusBadge status={item.execution_status} />
    <div className="provider-cell-compact"><ShieldIcon size={14} /><span>{item.provider_mode}</span></div>
    <div className="queue-row-actions">{executed ? <span className="muted-text">Complete</span> : <button className={`queue-action ${due ? "ready" : ""}`} type="button" onClick={onExecute} disabled={!due || pending} title={due ? "Execute eligible retry" : "Retry is not yet eligible"}>{pending ? "Executing…" : due ? "Execute" : "Not due"}</button>}</div>
  </div>;
}
