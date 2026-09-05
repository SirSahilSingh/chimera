"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRightIcon, CheckIcon, ClockIcon, CpuIcon, InfoIcon, RefreshIcon, ShieldIcon, ZapIcon } from "../../../components/icons";
import { DropdownField, ErrorState, LoadingState, StatusBadge } from "../../../components/shell";
import { IntelligenceMetric, IntelligencePanel, IntelligenceTitle } from "../../../components/intelligence-workspace";
import { api, ApiError } from "../../../lib/api";
import { formatDate, shortId } from "../../../lib/formatters";
import type { ScheduledRetry } from "../../../lib/types";

type RetryFilter = "ALL" | "SCHEDULED" | "DUE" | "EXECUTED";

function formatRelativeTime(dateStr: string) {
  const target = new Date(dateStr).getTime();
  const now = Date.now();
  const diffMs = target - now;
  const absDiffSec = Math.round(Math.abs(diffMs) / 1000);

  if (diffMs > 0) {
    if (absDiffSec < 60) return "Due in seconds";
    if (absDiffSec < 3600) return `Due in ${Math.round(absDiffSec / 60)}m`;
    if (absDiffSec < 86400) return `Due in ${Math.round(absDiffSec / 3600)}h`;
    return `Due in ${Math.round(absDiffSec / 86400)}d`;
  } else {
    if (absDiffSec < 60) return "Due now";
    if (absDiffSec < 3600) return `${Math.round(absDiffSec / 60)}m ago`;
    if (absDiffSec < 86400) return `${Math.round(absDiffSec / 3600)}h ago`;
    return `${Math.round(absDiffSec / 86400)}d ago`;
  }
}

export default function ScheduledRetriesPage() {
  const [retries, setRetries] = useState<ScheduledRetry[]>([]);
  const [filter, setFilter] = useState<RetryFilter>("ALL");
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      setRetries(await api.listScheduledRetries());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load scheduled retries.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(true), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const now = Date.now();
  const isDue = (item: ScheduledRetry) => item.execution_status === "SCHEDULED" && new Date(item.scheduled_at).getTime() <= now;

  const visible = useMemo(
    () =>
      retries.filter(
        (item) =>
          filter === "ALL" ||
          (filter === "DUE" && isDue(item)) ||
          (filter === "SCHEDULED" && item.execution_status === "SCHEDULED") ||
          (filter === "EXECUTED" && item.execution_status === "EXECUTED")
      ),
    [retries, filter]
  );

  const due = retries.filter(isDue).length;
  const scheduled = retries.filter((item) => item.execution_status === "SCHEDULED").length;
  const executed = retries.filter((item) => item.execution_status === "EXECUTED").length;
  const nextRetry = retries
    .filter((item) => item.execution_status === "SCHEDULED")
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())[0];

  const execute = async (item: ScheduledRetry) => {
    setPendingId(item.id);
    setNotice(null);
    setError(null);
    try {
      const result = await api.executeScheduledRetry(item.id, true);
      setNotice(`Retry attempt executed for case ${shortId(item.recovery_case_id)} · Status: ${result.status.replaceAll("_", " ")}.`);
      await load(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The scheduled retry could not be executed.");
    } finally {
      setPendingId(null);
    }
  };

  const seedDemoRetry = async () => {
    setSeeding(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.runDemo({
        scenario: "technical_retry",
        provider_mode: "LOCAL",
      });
      setNotice(`Created deterministic technical retry case ${shortId(result.case_id)}. Schedule added!`);
      await load(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create demo retry scenario.");
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="operations-page queue-surface scheduled-retries-page">
      <IntelligenceTitle
        title="Scheduled Retries"
        action={
          <div className="title-action-cluster">
            <button
              className="button button-primary"
              type="button"
              onClick={seedDemoRetry}
              disabled={seeding || loading}
            >
              <CpuIcon size={14} />
              <span>{seeding ? "Creating Schedule…" : "+ New Test Schedule"}</span>
            </button>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void load()}
              disabled={loading}
              aria-label="Refresh scheduled retries"
            >
              <RefreshIcon size={14} className={loading ? "animate-spin" : ""} />
              <span>Refresh</span>
            </button>
          </div>
        }
      />

      <div className="workspace-meta standalone-meta">
        <span>Autonomous Backoff Policy</span>
        <span>{retries.length} Stored Schedules</span>
        <span>Deterministic Idempotency Enforced</span>
      </div>

      <section className="intelligence-metric-grid" aria-label="Scheduled retry summary">
        <IntelligenceMetric label="Scheduled Pending" value={String(scheduled)} note="Waiting for execution window" />
        <IntelligenceMetric label="Due Now" value={String(due)} note="Eligible under schedule window" tone={due ? "amber" : "default"} />
        <IntelligenceMetric label="Executed" value={String(executed)} note="Processed retry attempts" tone={executed ? "mint" : "default"} />
        <IntelligenceMetric
          label="Next Scheduled Window"
          value={nextRetry ? formatRelativeTime(nextRetry.scheduled_at) : "—"}
          note={nextRetry ? formatDate(nextRetry.scheduled_at) : "No pending schedules"}
        />
      </section>

      <IntelligencePanel title="Retry Schedule Registry" note={`${visible.length} ${visible.length === 1 ? "record" : "records"}`}>
        <div className="queue-toolbar queue-toolbar-inline">
          <div>
            <strong>Deterministic Retry Backoff Queue</strong>
            <span>Autonomous schedule triggered when decision engine selects RETRY_LATER.</span>
          </div>

          <div className="queue-filters">
            <DropdownField
              className="queue-filter"
              label="View"
              value={filter}
              onChange={(val) => setFilter(val as RetryFilter)}
              options={[
                { value: "ALL", label: `All Schedules (${retries.length})` },
                { value: "SCHEDULED", label: `Pending (${scheduled})`, tone: "blue" },
                { value: "DUE", label: `Due Now (${due})`, tone: "amber" },
                { value: "EXECUTED", label: `Executed (${executed})`, tone: "mint" },
              ]}
            />
          </div>
        </div>

        {error && <ErrorState message={error} onRetry={load} />}
        {notice && (
          <div className="queue-notice">
            <CheckIcon size={15} />
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss notification">
              Dismiss
            </button>
          </div>
        )}

        {!loading && !visible.length && (
          <div className="retries-empty-state">
            <div className="empty-icon-wrap">
              <ClockIcon size={28} />
            </div>
            <h3>No Scheduled Retries Stored</h3>
            <p>
              When transient payment errors or technical degradations occur, the decision engine autonomously schedules a deterministic retry window.
            </p>
            <button className="button button-primary" type="button" onClick={seedDemoRetry} disabled={seeding}>
              <CpuIcon size={14} />
              <span>{seeding ? "Generating Schedule…" : "Generate Demo Technical Retry Scenario"}</span>
            </button>
          </div>
        )}

        {visible.length > 0 && (
          <div className="operations-queue-table">
            <div className="operations-queue-row retry-queue-header">
              <span>Schedule Timing</span>
              <span>Case Reference</span>
              <span>Reason / Policy</span>
              <span>Eligibility</span>
              <span>Status</span>
              <span>Provider</span>
              <span className="text-right">Action</span>
            </div>

            {visible.map((item) => {
              const executed = item.execution_status === "EXECUTED";
              const itemDue = isDue(item);
              const isPending = pendingId === item.id;
              const isExpanded = expandedId === item.id;

              return (
                <div key={item.id} className="retry-row-container">
                  <div className="operations-queue-row retry-queue-row">
                    <div className="retry-time-cell">
                      <ClockIcon size={16} />
                      <div>
                        <strong>{formatDate(item.scheduled_at)}</strong>
                        <span className="relative-badge">{formatRelativeTime(item.scheduled_at)}</span>
                      </div>
                    </div>

                    <Link className="queue-case-cell" href={`/cases/${item.recovery_case_id}`}>
                      <strong>{shortId(item.recovery_case_id)}</strong>
                      <span>Case details <ArrowRightIcon size={11} /></span>
                    </Link>

                    <div className="queue-reason-cell">
                      <strong>{item.schedule_reason.replaceAll("_", " ")}</strong>
                      <span>Attempt #{item.attempt_number}</span>
                    </div>

                    <div>
                      <StatusBadge status={item.eligibility_status} />
                    </div>

                    <div>
                      <StatusBadge status={item.execution_status} />
                    </div>

                    <div className="provider-cell-compact">
                      <ShieldIcon size={14} />
                      <span>{item.provider_mode}</span>
                    </div>

                    <div className="queue-row-actions">
                      {executed ? (
                        <div className="executed-badge-chip">
                          <CheckIcon size={13} />
                          <span>Complete</span>
                        </div>
                      ) : (
                        <button
                          className="button button-primary queue-execute-btn"
                          type="button"
                          onClick={() => execute(item)}
                          disabled={isPending}
                          title={itemDue ? "Execute due retry attempt" : "Trigger retry attempt immediately (Operator Override)"}
                        >
                          <ZapIcon size={13} />
                          <span>{isPending ? "Executing…" : "Execute Now"}</span>
                        </button>
                      )}

                      <button
                        className="button button-quiet btn-details-toggle"
                        type="button"
                        onClick={() => setExpandedId(isExpanded ? null : item.id)}
                      >
                        {isExpanded ? "Hide" : "Details"}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Diagnostics Drawer */}
                  {isExpanded && (
                    <div className="retry-expanded-drawer">
                      <div className="expanded-grid">
                        <div>
                          <span className="drawer-label">Schedule ID</span>
                          <code>{item.id}</code>
                        </div>
                        <div>
                          <span className="drawer-label">Intervention ID</span>
                          <code>{item.intervention_id}</code>
                        </div>
                        <div>
                          <span className="drawer-label">Idempotency Key</span>
                          <code>{item.idempotency_key}</code>
                        </div>
                        <div>
                          <span className="drawer-label">Executed At</span>
                          <span>{item.executed_at ? formatDate(item.executed_at) : "Pending execution window"}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </IntelligencePanel>

      <div className="queue-footnote">
        <StatusBadge status="OPERATIONAL" />
        <span>
          Retry timing and eligibility are governed by the deterministic backoff policy. Operators can trigger immediate execution at any time to verify retry recovery flows.
        </span>
        <Link href="/system/decision-engine">
          View decision engine <ArrowRightIcon size={14} />
        </Link>
      </div>
    </div>
  );
}
