"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertIcon, ArrowRightIcon, CheckIcon, RefreshIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../components/intelligence-workspace";
import { api, ApiError } from "../../lib/api";
import { formatDate, formatPaise, shortId } from "../../lib/formatters";
import type { Escalation } from "../../lib/types";

type EscalationFilter = "ALL" | "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "RESOLVED" | "CANCELLED";

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [filter, setFilter] = useState<EscalationFilter>("ALL");
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setEscalations(await api.listEscalations());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load escalations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const visible = useMemo(() => filter === "ALL" ? escalations : escalations.filter((item) => item.status === filter), [escalations, filter]);
  const open = escalations.filter((item) => item.status === "OPEN").length;
  const active = escalations.filter((item) => item.status === "ACKNOWLEDGED" || item.status === "IN_PROGRESS").length;
  const openValue = escalations.filter((item) => item.status !== "RESOLVED" && item.status !== "CANCELLED").reduce((sum, item) => sum + numberValue(item.context_json.amount_paise), 0);
  const highestPriority = escalations.length ? Math.max(...escalations.map((item) => item.priority)) : 0;

  const transition = async (item: Escalation, action: "acknowledge" | "resolve") => {
    setPendingId(item.id);
    setNotice(null);
    try {
      const updated = action === "acknowledge" ? await api.acknowledgeEscalation(item.id) : await api.resolveEscalation(item.id);
      setEscalations((current) => current.map((candidate) => candidate.id === updated.id ? updated : candidate));
      setNotice(action === "acknowledge" ? "Escalation acknowledged and assigned to the operator queue." : "Escalation marked resolved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The escalation could not be updated.");
    } finally {
      setPendingId(null);
    }
  };

  return <div className="operations-page queue-surface">
    <IntelligenceTitle title="Escalations" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh escalations"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More escalation actions"><span className="more-dots">•••</span></button></>} />
    <div className="workspace-meta standalone-meta"><span>Data: synthetic stored records</span><span>{escalations.length} escalation records</span><span>Operator queue</span></div>

    <section className="intelligence-metric-grid" aria-label="Escalation summary">
      <IntelligenceMetric label="Open now" value={String(open)} note="Awaiting acknowledgment" tone={open ? "amber" : "default"} />
      <IntelligenceMetric label="In operator flow" value={String(active)} note="Acknowledged or in progress" />
      <IntelligenceMetric label="Value exposed" value={formatPaise(openValue)} note="Open escalation context" tone={openValue ? "amber" : "default"} />
      <IntelligenceMetric label="Highest priority" value={highestPriority ? `P${highestPriority}` : "—"} note={highestPriority ? "Stored escalation priority" : "No priority recorded"} />
    </section>

    <IntelligencePanel title="Operator queue" note={`${visible.length} ${visible.length === 1 ? "record" : "records"}`}>
      <div className="queue-toolbar queue-toolbar-inline">
        <div><strong>Human review records</strong><span>Every action creates an append-only escalation event.</span></div>
        <label className="queue-filter"><span>Status</span><select value={filter} onChange={(event) => setFilter(event.target.value as EscalationFilter)}><option value="ALL">All statuses</option><option value="OPEN">Open</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option><option value="CANCELLED">Cancelled</option></select></label>
      </div>
      {error ? <ErrorState message={error} onRetry={load} /> : loading ? <LoadingState label="Loading escalation queue" /> : notice ? <div className="queue-notice"><CheckIcon size={15} /><span>{notice}</span><button type="button" onClick={() => setNotice(null)} aria-label="Dismiss notification">Dismiss</button></div> : null}
      {!loading && !error && <div className="operations-queue-table"><div className="operations-queue-row operations-queue-header"><span>Priority</span><span>Case</span><span>Reason</span><span>Status</span><span>Created</span><span>Events</span><span /></div>{visible.map((item) => <EscalationRow item={item} pending={pendingId === item.id} onAcknowledge={() => void transition(item, "acknowledge")} onResolve={() => void transition(item, "resolve")} key={item.id} />)}</div>}
      {!loading && !error && !visible.length && <IntelEmpty label={filter === "ALL" ? "No escalations are stored yet. Create an ESCALATE intervention from a Decision Room to open a real operator record." : "No escalations match this status filter."} />}
    </IntelligencePanel>

    <div className="queue-footnote"><StatusBadge status="LOCAL" /><span>Escalations are persisted locally for the demo and remain auditable through their event history.</span><Link href="/audit">Open audit trail <ArrowRightIcon size={14} /></Link></div>
  </div>;
}

function EscalationRow({ item, pending, onAcknowledge, onResolve }: { item: Escalation; pending: boolean; onAcknowledge: () => void; onResolve: () => void }) {
  const terminal = item.status === "RESOLVED" || item.status === "CANCELLED";
  return <div className="operations-queue-row">
    <div className={`priority-cell priority-${item.priority >= 4 ? "high" : item.priority >= 2 ? "medium" : "low"}`}><strong>P{item.priority}</strong><span>{item.priority >= 4 ? "High" : item.priority >= 2 ? "Normal" : "Low"}</span></div>
    <Link className="queue-case-cell" href={`/cases/${item.recovery_case_id}`}><strong>{shortId(item.recovery_case_id)}</strong><span>{shortId(item.id)}</span></Link>
    <div className="queue-reason-cell"><strong>{item.escalation_reason}</strong><span>{item.provider_mode} · {numberValue(item.context_json.amount_paise) ? formatPaise(numberValue(item.context_json.amount_paise), String(item.context_json.currency ?? "INR")) : "Amount not recorded"}</span></div>
    <StatusBadge status={item.status} />
    <span className="queue-time">{formatDate(item.created_at)}</span>
    <details className="queue-events"><summary>{item.events.length} {item.events.length === 1 ? "event" : "events"}</summary><div>{item.events.map((event) => <span key={event.id}>{event.event_type.replaceAll("_", " ")} · {event.actor}</span>)}</div></details>
    <div className="queue-row-actions">{item.status === "OPEN" && <button className="queue-action" type="button" onClick={onAcknowledge} disabled={pending}>Acknowledge</button>}{!terminal && item.status !== "OPEN" && <button className="queue-action" type="button" onClick={onResolve} disabled={pending}>Resolve</button>}{terminal && <span className="muted-text">Closed</span>}</div>
  </div>;
}

function numberValue(value: unknown) {
  return typeof value === "number" ? value : Number(value ?? 0);
}
