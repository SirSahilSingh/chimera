"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { RecoveryCase } from "../../lib/types";
import { AuditIcon } from "../../components/icons";
import { ErrorState, LoadingState, PageHeader } from "../../components/shell";
import { RecoveryActivityFeed } from "../../components/operational";

export default function AuditPage() {
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.listCases({ page: 1, pageSize: 100 }).then((response) => setCases(response.items)).catch((err) => setError(err instanceof ApiError ? err.detail : "Could not load the audit trail.")).finally(() => setLoading(false)); }, []);
  return <div className="audit-page"><PageHeader eyebrow="System record" title="Audit Trail" description="A chronological view of stored case, decision, execution, and outcome milestones." />{error ? <ErrorState message={error} /> : loading ? <LoadingState label="Loading audit trail" /> : !cases.length ? <div className="empty-state"><h3>No audit events recorded</h3><p>Stored case milestones will appear here once the recovery API receives events.</p></div> : <><section className="audit-banner"><AuditIcon size={19} /><div><strong>Stored deterministic decisions remain authoritative.</strong><p>The explanation layer is informational only. This view contains only milestones returned by the existing recovery-case API.</p></div></section><RecoveryActivityFeed cases={cases} /></>}</div>;
}
