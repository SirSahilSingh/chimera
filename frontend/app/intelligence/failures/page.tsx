"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import type { RecoveryCase } from "../../../lib/types";
import { formatPaise } from "../../../lib/formatters";
import { isUnresolved } from "../../../lib/operations";
import { ErrorState, LoadingState, PageHeader } from "../../../components/shell";
import { FailureBreakdown, RootCauseInsight } from "../../../components/operational";

export default function FailureIntelligencePage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.listCases({ page: 1, pageSize: 100 }).then((response) => setCases(response.items)).catch((err) => setError(err instanceof ApiError ? err.detail : "Could not load failure intelligence.")).finally(() => setLoading(false)); }, []);
  if (error) return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Failure Intelligence" description="Understand where observable payment failures are putting revenue at risk." /><ErrorState message={error} /></div>;
  if (loading) return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Failure Intelligence" description="Understand where observable payment failures are putting revenue at risk." /><LoadingState label="Loading failure patterns" /></div>;
  if (!cases.length) return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Failure Intelligence" description="Understand where observable payment failures are putting revenue at risk." /><div className="empty-state"><h3>No failure patterns recorded</h3><p>Stored cases will appear here once the recovery API receives payment failures.</p></div></div>;
  const unresolved = cases.filter(isUnresolved);
  return <div className="intelligence-page"><PageHeader eyebrow="Intelligence" title="Failure Intelligence" description="Understand where observable payment failures are putting revenue at risk." /><section className="intelligence-hero"><div><span className="section-overline">Observed system pressure</span><strong>{formatPaise(unresolved.reduce((sum, item) => sum + item.amount_paise, 0))}</strong><p>Revenue currently associated with unresolved failures.</p></div><div><span className="section-overline">Cases in view</span><strong>{cases.length}</strong><p>Only stored API cases are included.</p></div><div><span className="section-overline">Data boundary</span><strong>Observable</strong><p>No hidden segment, future outcome, or fabricated trend.</p></div></section><FailureBreakdown cases={cases} /><RootCauseInsight cases={cases} /></div>;
}
