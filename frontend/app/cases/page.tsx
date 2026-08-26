"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { RecoveryCase } from "../../lib/types";
import { formatAction, formatFailureReason } from "../../lib/formatters";
import { isActiveRecovery, isRecovered, isUnresolved } from "../../lib/operations";
import { RefreshIcon } from "../../components/icons";
import { Button, ErrorState, LoadingState, PageHeader } from "../../components/shell";
import { CaseTable } from "../../components/case-table";

type CaseFilter = "all" | "active" | "recovered" | "escalated" | "unresolved";

export default function CasesPage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [filter, setFilter] = useState<CaseFilter>("all");
  const [failureReason, setFailureReason] = useState("");
  const [intervention, setIntervention] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = async () => { setLoading(true); setError(null); try { const response = await api.listCases({ page: 1, pageSize: 100 }); setCases(response.items); } catch (err) { setError(err instanceof ApiError ? err.detail : "Could not load recovery cases."); } finally { setLoading(false); } };
  useEffect(() => { const params = new URLSearchParams(window.location.search); if (params.get("status") === "DECIDED") setFilter("active"); if (params.get("failure_reason")) setFailureReason(params.get("failure_reason") ?? ""); load(); }, []);

  const failureOptions = useMemo(() => Array.from(new Set(cases.map((item) => item.failure_reason))).sort(), [cases]);
  const actionOptions = useMemo(() => Array.from(new Set(cases.map((item) => item.latest_decision?.selected_action).filter((item): item is string => Boolean(item)))).sort(), [cases]);
  const visibleCases = useMemo(() => cases.filter((item) => {
    const statusMatch = filter === "all" || filter === "active" && isActiveRecovery(item) || filter === "recovered" && isRecovered(item) || filter === "unresolved" && isUnresolved(item) || filter === "escalated" && (item.status === "UNRECOVERED" || item.latest_decision?.selected_action === "ESCALATE");
    return statusMatch && (!failureReason || item.failure_reason === failureReason) && (!intervention || item.latest_decision?.selected_action === intervention);
  }), [cases, filter, failureReason, intervention]);

  return <div className="cases-page"><PageHeader eyebrow="Recovery operations" title="Recovery cases" description="Follow each payment failure from detection through intervention and outcome." action={<Button kind="secondary" onClick={load} disabled={loading}><RefreshIcon size={15} />Refresh</Button>} />
    <div className="cases-command-bar"><div><span>Loaded workspace</span><strong>{visibleCases.length} <small>of {cases.length} cases</small></strong></div><div className="filter-set" aria-label="Recovery case filters"><Filter label="View" value={filter} onChange={(value) => setFilter(value as CaseFilter)} options={[{ value: "all", label: "All cases" }, { value: "active", label: "Active recovery" }, { value: "recovered", label: "Recovered" }, { value: "escalated", label: "Escalated" }, { value: "unresolved", label: "Unresolved" }]} /><Filter label="Failure" value={failureReason} onChange={setFailureReason} options={[{ value: "", label: "All failure patterns" }, ...failureOptions.map((value) => ({ value, label: formatFailureReason(value) }))]} /><Filter label="Intervention" value={intervention} onChange={setIntervention} options={[{ value: "", label: "All interventions" }, ...actionOptions.map((value) => ({ value, label: formatAction(value) }))]} /></div></div>
    {error ? <ErrorState message={error} onRetry={load} /> : loading ? <LoadingState label="Loading recovery operations" /> : <section className="cases-table-block"><CaseTable cases={visibleCases} /></section>}
  </div>;
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[] }) {
  return <label className="filter-control"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>;
}
