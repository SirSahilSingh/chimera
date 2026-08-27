"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "../lib/api";
import type { ProviderReadiness, RecoveryCase } from "../lib/types";
import { formatAction, formatFailureReason, formatPaise, formatPercent } from "../lib/formatters";
import { isActiveRecovery, isRecovered, isUnresolved } from "../lib/operations";
import { ArrowRightIcon, RefreshIcon } from "../components/icons";
import { Button, ErrorState, LoadingState, PageHeader, StatusBadge } from "../components/shell";
import { CaseTable } from "../components/case-table";
import { FailureBreakdown, OperationsDistribution, RecoveryActivityFeed, RootCauseInsight } from "../components/operational";
import { DemoLauncher } from "../components/demo-launcher";

export default function CommandCenter() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [providers, setProviders] = useState<ProviderReadiness[]>([]);
  const load = async () => { setLoading(true); setError(null); try { const [response, readiness] = await Promise.all([api.listCases({ page: 1, pageSize: 100 }), api.providerReadiness()]); setCases(response.items); setTotal(response.total); setProviders(readiness); } catch (err) { setError(err instanceof ApiError ? err.detail : "Could not load recovery operations."); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);

  const stats = useMemo(() => {
    const unresolved = cases.filter(isUnresolved);
    const recovered = cases.filter(isRecovered);
    const eligible = recovered.length + cases.filter((item) => item.status === "UNRECOVERED").length;
    const patterns = new Map<string, { count: number; amount: number; sample: RecoveryCase }>();
    for (const item of unresolved) { const pattern = patterns.get(item.failure_reason) ?? { count: 0, amount: 0, sample: item }; pattern.count += 1; pattern.amount += item.amount_paise; patterns.set(item.failure_reason, pattern); }
    const topPattern = Array.from(patterns.entries()).sort((a, b) => b[1].amount - a[1].amount)[0];
    const selected = cases.filter((item) => item.latest_decision).reduce<Record<string, number>>((result, item) => { const action = item.latest_decision?.selected_action; if (action) result[action] = (result[action] ?? 0) + 1; return result; }, {});
    return { risk: unresolved.reduce((sum, item) => sum + item.amount_paise, 0), recoveredValue: recovered.reduce((sum, item) => sum + item.amount_paise, 0), active: cases.filter(isActiveRecovery).length, recoveryRate: eligible ? recovered.length / eligible : null, topPattern, mostSelected: Object.entries(selected).sort((a, b) => b[1] - a[1])[0]?.[0] };
  }, [cases]);

  return <div className="dashboard-page"><PageHeader eyebrow="Autonomous recovery operations" title="Revenue Recovery Command Center" description="Monitor payment failures, diagnose observable patterns, and track CHIMERA interventions." action={<Button kind="secondary" onClick={load} disabled={loading}><RefreshIcon size={15} />Refresh</Button>} />
    {error && <ErrorState message={error} onRetry={load} />}
    {loading ? <LoadingState label="Loading recovery intelligence" /> : <>
      <section className="command-hero"><div className="hero-thesis"><span className="hero-kicker"><span className="status-dot online" />Synthetic environment</span><h2>What is going wrong right now, and what is CHIMERA doing about it?</h2><div className="workflow-strip"><span>Detect</span><i>→</i><span>Diagnose</span><i>→</i><span>Decide</span><i>→</i><span className="current">Intervene</span><i>→</i><span>Recover</span></div></div><div className="hero-readout"><span>Revenue currently at risk</span><strong>{formatPaise(stats.risk)}</strong><small>Across {cases.filter(isUnresolved).length} unresolved stored cases</small><Link href="/cases" className="hero-link">Open recovery operations <ArrowRightIcon size={15} /></Link></div></section>
      <section className="command-kpis" aria-label="Recovery metrics"><Metric label="Revenue at risk" value={formatPaise(stats.risk)} note="Unresolved failures" tone="risk" /><Metric label="Recovered" value={formatPaise(stats.recoveredValue)} note="Stored RECOVERED status" tone="mint" /><Metric label="Active recovery" value={`${stats.active} cases`} note="Decided or intervening" tone="amber" /><Metric label="Recovery rate" value={stats.recoveryRate === null ? "—" : formatPercent(stats.recoveryRate)} note="Observed resolved outcomes" tone="blue" /></section>
      <section className="provider-readiness-panel"><div className="panel-heading"><div><span className="section-overline">Integration posture</span><h2>Provider readiness</h2></div><span className="panel-note">No customer-facing action is triggered</span></div><div className="provider-readiness-grid">{providers.map((provider) => <div className="provider-readiness-card" key={provider.provider_name}><div className="provider-readiness-head"><div><span>{provider.provider_type}</span><strong>{provider.provider_name}</strong></div><StatusBadge status={provider.readiness_status} /></div><p><b>{provider.provider_mode}</b> · {provider.implementation} · {provider.capabilities.length} capabilities</p><small>{provider.last_verification_timestamp ? `Verified ${new Date(provider.last_verification_timestamp).toLocaleString()}` : "Verification not run"}</small><div className="provider-readiness-limits">{provider.limitations[0]}</div></div>)}</div><div className="provider-readiness-note">LOCAL / MOCK / TEST are never LIVE_VERIFIED. A live status requires an actual successful provider request and explicit <code>CHIMERA_ALLOW_LIVE_EXECUTION=true</code>.</div></section>
      <section className="incident-panel"><div className="panel-heading"><div><span className="section-overline">What CHIMERA is seeing</span><h2>Active problem signal</h2></div><span className="panel-note">Derived from observable case fields</span></div>{stats.topPattern ? <div className="incident-flow"><div className="incident-node"><span>Problem</span><strong>{formatFailureReason(stats.topPattern[0])}</strong><small>{stats.topPattern[1].count} unresolved cases · {formatPaise(stats.topPattern[1].amount)} at risk</small></div><ArrowRightIcon size={18} /><div className="incident-node"><span>Diagnosis</span><strong>Observed failure pattern</strong><small>{stats.topPattern[1].sample.incident_flag ? "Incident signal is active" : "No incident signal recorded"}</small></div><ArrowRightIcon size={18} /><div className="incident-node response"><span>CHIMERA response</span><strong>{stats.topPattern[1].sample.latest_decision ? formatAction(stats.topPattern[1].sample.latest_decision.selected_action) : "Awaiting decision"}</strong><small>{stats.topPattern[1].sample.latest_decision ? "Stored deterministic intervention" : "Decision has not been generated"}</small></div></div> : <div className="inline-empty"><span className="empty-orbit" /><span>No unresolved failure signal is available in the loaded workspace.</span></div>}</section>
      <DemoLauncher />
      <OperationsDistribution cases={cases} />
      <div className="dashboard-grid"><FailureBreakdown cases={cases} /><RootCauseInsight cases={cases} /></div>
      <div className="dashboard-grid lower"><RecoveryActivityFeed cases={cases.slice(0, 8)} /><section className="recent-panel"><div className="panel-heading"><div><span className="section-overline">Operations</span><h2>Recent recovery cases</h2></div><Link href="/cases" className="panel-link">View all <ArrowRightIcon size={15} /></Link></div>{cases.length ? <CaseTable cases={cases.slice(0, 5)} compact /> : <div className="inline-empty"><span className="empty-orbit" /><span>Cases created through the API will appear here.</span></div>}</section></div>
      <section className="command-footer"><div><span className="section-overline">Decision posture</span><strong>Stored decisions remain authoritative.</strong><p>The browser shows the trace, explanation, and execution state. It never recalculates the recovery decision.</p></div><div className="footer-readout"><span>Most selected intervention</span><strong>{stats.mostSelected ? formatAction(stats.mostSelected) : "—"}</strong></div><div className="footer-readout"><span>Cases loaded</span><strong>{total}</strong></div></section>
    </>}
  </div>;
}

function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone: "risk" | "mint" | "amber" | "blue" }) {
  return <div className={`metric-block ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}
