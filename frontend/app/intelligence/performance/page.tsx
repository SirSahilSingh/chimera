"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import type { RecoveryCase } from "../../../lib/types";
import { formatPaise, formatPercent } from "../../../lib/formatters";
import { isRecovered } from "../../../lib/operations";
import { ErrorState, LoadingState, PageHeader } from "../../../components/shell";
import { InterventionPerformance } from "../../../components/operational";

export default function RecoveryPerformancePage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.listCases({ page: 1, pageSize: 100 }).then((response) => setCases(response.items)).catch((err) => setError(err instanceof ApiError ? err.detail : "Could not load recovery performance.")).finally(() => setLoading(false)); }, []);
  const stats = useMemo(() => { const recovered = cases.filter(isRecovered); const resolved = recovered.length + cases.filter((item) => item.status === "UNRECOVERED").length; return { atRisk: cases.filter((item) => !isRecovered(item) && item.status !== "CLOSED").reduce((sum, item) => sum + item.amount_paise, 0), recovered: recovered.reduce((sum, item) => sum + item.amount_paise, 0), unresolved: cases.filter((item) => item.status === "UNRECOVERED").reduce((sum, item) => sum + item.amount_paise, 0), rate: resolved ? recovered.length / resolved : null }; }, [cases]);
  if (error) return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Recovery Performance" description="Review observed outcomes by stored intervention." /><ErrorState message={error} /></div>;
  if (loading) return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Recovery Performance" description="Review observed outcomes by stored intervention." /><LoadingState label="Loading observed outcomes" /></div>;
  if (!cases.length) return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Recovery Performance" description="Review observed outcomes by stored intervention." /><div className="empty-state"><h3>No observed outcomes recorded</h3><p>Stored decisions and outcomes will appear here after recovery cases move through the lifecycle.</p></div></div>;
  return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Recovery Performance" description="Review observed outcomes by stored intervention, without claiming causal superiority." /><section className="performance-hero"><Metric label="Revenue at risk" value={formatPaise(stats.atRisk)} /><Metric label="Recovered revenue" value={formatPaise(stats.recovered)} tone="mint" /><Metric label="Unresolved value" value={formatPaise(stats.unresolved)} tone="risk" /><Metric label="Observed recovery rate" value={stats.rate === null ? "—" : formatPercent(stats.rate)} tone="blue" /></section><InterventionPerformance cases={cases} /><div className="method-note"><span className="status-dot" /><div><strong>Interpretation boundary</strong><p>These are observed recovery outcomes from synthetic stored cases. This view does not establish that an intervention caused the outcome or claims real-world predictive performance.</p></div></div></div>;
}

function Metric({ label, value, tone = "default" }: { label: string; value: string; tone?: string }) { return <div className={`performance-metric ${tone}`}><span>{label}</span><strong>{value}</strong></div>; }
