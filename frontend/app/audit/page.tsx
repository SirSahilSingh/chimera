"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { JourneyEvent, RecoveryCase } from "../../lib/types";
import { formatDate } from "../../lib/formatters";
import { ArrowRightIcon, AuditIcon, RefreshIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { EvidenceBoundary, IntelligenceTitle, IntelEmpty } from "../../components/intelligence-workspace";

type AuditRow = JourneyEvent & { caseRef: string; caseId: string; caseStatus: string; decisionRef: string };

export default function AuditPage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [events, setEvents] = useState<AuditRow[]>([]);
  const [eventType, setEventType] = useState("");
  const [source, setSource] = useState("");
  const [providerMode, setProviderMode] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listCases({ page: 1, pageSize: 100 });
      const rows = await Promise.all(response.items.map(async (item) => {
        try {
          const journey = await api.getJourney(item.id);
          return journey.audit_trail.map((event) => ({ ...event, caseRef: item.external_event_id || item.id, caseId: item.id, caseStatus: item.status, decisionRef: item.latest_decision?.id ?? "—" }));
        } catch {
          return [];
        }
      }));
      setCases(response.items);
      setEvents(rows.flat().sort((a, b) => new Date(b.timestamp ?? 0).getTime() - new Date(a.timestamp ?? 0).getTime()));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load the audit trail.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const eventTypes = useMemo(() => Array.from(new Set(events.map((event) => event.event_type))).sort(), [events]);
  const sources = useMemo(() => Array.from(new Set(events.map((event) => event.source))).sort(), [events]);
  const providerModes = useMemo(() => Array.from(new Set(events.map((event) => event.provider_mode).filter((item): item is string => Boolean(item)))).sort(), [events]);
  const visibleEvents = events.filter((event) => (!eventType || event.event_type === eventType) && (!source || event.source === source) && (!providerMode || event.provider_mode === providerMode));
  const auditContent = visibleEvents.length ? <div className="audit-table"><div className="audit-row audit-row-header"><span>Timestamp</span><span>Event</span><span>Source</span><span>Case</span><span>Decision</span><span>Provider mode</span><span>Status</span><span /></div>{visibleEvents.map((event) => <div className="audit-row" key={event.id}><span className="audit-time">{event.timestamp ? formatDate(event.timestamp) : "Timestamp unavailable"}</span><strong>{event.event_type.replaceAll("_", " ")}</strong><span>{event.source}</span><a href={`/cases/${event.caseId}`}>{event.caseRef}</a><span className="audit-code">{event.decisionRef}</span><span className="mode-label">{event.provider_mode ?? "—"}</span><StatusBadge status={event.caseStatus} /><a className="audit-open" href={`/cases/${event.caseId}`} aria-label={`Open ${event.caseRef}`}><ArrowRightIcon size={14} /></a></div>)}</div> : <IntelEmpty label={events.length ? "No events match the current filters." : "No persisted audit events are available yet."} />;

  if (loading) return <div className="system-page"><IntelligenceTitle title="Audit Trail" /><LoadingState label="Loading audit trail" /></div>;
  if (error) return <div className="system-page"><IntelligenceTitle title="Audit Trail" /><ErrorState message={error} onRetry={load} /></div>;

  return <div className="system-page">
    <IntelligenceTitle title="Audit Trail" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh audit trail"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More audit actions"><span className="more-dots">•••</span></button></>} />
    <EvidenceBoundary sampleSize={cases.length} lastUpdated="On refresh" />
    <div className="audit-banner"><AuditIcon size={17} /><div><strong>Append-only operational record</strong><span>Events are read from persisted recovery journeys. The audit surface never edits or reorders source records.</span></div></div>
    <section className="audit-workspace"><div className="audit-toolbar"><strong>{visibleEvents.length} events</strong><div className="audit-filters"><AuditFilter label="Event" value={eventType} onChange={setEventType} options={eventTypes} /><AuditFilter label="Source" value={source} onChange={setSource} options={sources} /><AuditFilter label="Mode" value={providerMode} onChange={setProviderMode} options={providerModes} /></div></div>{auditContent}</section>
    <div className="system-footnote"><AuditIcon size={15} /><span>Payload details stay sanitized. Full case evidence remains available in the Decision Room.</span></div>
  </div>;
}

function AuditFilter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return <label className="audit-filter"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}><option value="">All</option>{options.map((option) => <option value={option} key={option}>{option.replaceAll("_", " ")}</option>)}</select></label>;
}
