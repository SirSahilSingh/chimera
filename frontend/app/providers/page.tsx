"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { ProviderReadiness } from "../../lib/types";
import { formatDate } from "../../lib/formatters";
import { CheckIcon, RefreshIcon, ShieldIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { IntelligencePanel, IntelligenceTitle, IntelEmpty } from "../../components/intelligence-workspace";

export default function ProvidersPage() {
  const [providers, setProviders] = useState<ProviderReadiness[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setProviders(await api.providerReadiness());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load provider readiness.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const ready = useMemo(() => providers.filter((item) => item.readiness_status.endsWith("_VERIFIED") || item.readiness_status === "READY" || item.readiness_status === "CONFIGURED").length, [providers]);
  const needsAttention = providers.filter((item) => ["FAILED", "UNAVAILABLE", "NOT_CONFIGURED"].includes(item.readiness_status)).length;

  const verify = async (provider: ProviderReadiness) => {
    setVerifying(provider.provider_name);
    setMessage(null);
    try {
      const result = await api.verifyProvider(provider.provider_name);
      setMessage(`${provider.provider_name}: ${result.message}`);
      await load();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.detail : "Provider verification failed.");
    } finally {
      setVerifying(null);
    }
  };

  if (loading) return <div className="provider-page"><IntelligenceTitle title="Provider Readiness" /><LoadingState label="Loading provider readiness" /></div>;
  if (error) return <div className="provider-page"><IntelligenceTitle title="Provider Readiness" /><ErrorState message={error} onRetry={load} /></div>;

  return <div className="provider-page">
    <IntelligenceTitle title="Provider Readiness" action={<><button className="square-control" type="button" onClick={load} disabled={loading} aria-label="Refresh provider readiness"><RefreshIcon size={16} /></button><button className="square-control" type="button" aria-label="More provider actions"><span className="more-dots">•••</span></button></>} />
    <div className="provider-summary"><div><span className="health-orb success" /><div><strong>External execution control plane</strong><small>Readiness is separate from recovery outcomes.</small></div></div><div className="provider-summary-count"><strong>{ready}/{providers.length}</strong><span>ready</span></div></div>
    {message && <div className="provider-message"><CheckIcon size={15} /><span>{message}</span></div>}
    <section className="provider-stat-grid"><ProviderStat label="Providers registered" value={String(providers.length)} /><ProviderStat label="Ready" value={String(ready)} tone="mint" /><ProviderStat label="Needs attention" value={String(needsAttention)} tone={needsAttention ? "amber" : "default"} /></section>
    <IntelligencePanel title="Readiness matrix" note="Safe provider metadata only"><div className="provider-matrix">{providers.length ? providers.map((provider) => <ProviderRow key={provider.provider_name} provider={provider} verifying={verifying === provider.provider_name} onVerify={() => verify(provider)} />) : <IntelEmpty label="No providers are registered in this environment." />}</div></IntelligencePanel>
    <div className="provider-boundary"><ShieldIcon size={15} /><span>Provider readiness means an assigned dependency can be probed. It never means a payment recovered.</span></div>
  </div>;
}

function ProviderStat({ label, value, tone = "default" }: { label: string; value: string; tone?: string }) {
  return <div className={`provider-stat ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

function ProviderRow({ provider, verifying, onVerify }: { provider: ProviderReadiness; verifying: boolean; onVerify: () => void }) {
  return <article className="provider-row"><div className="provider-main"><span className="provider-icon"><ShieldIcon size={16} /></span><div><strong>{provider.provider_name}</strong><small>{provider.implementation} · {provider.provider_type}</small></div></div><div className="provider-cell"><span>Mode</span><strong>{provider.provider_mode}</strong></div><div className="provider-cell"><span>Readiness</span><StatusBadge status={provider.readiness_status} /></div><div className="provider-cell provider-capabilities"><span>Capabilities</span><strong>{provider.capabilities.length ? provider.capabilities.slice(0, 2).join(" · ") : "None reported"}</strong></div><div className="provider-cell"><span>Last verified</span><strong>{provider.last_verification_timestamp ? formatDate(provider.last_verification_timestamp) : "Not verified"}</strong></div><div className="provider-cell"><span>Latency</span><strong>{provider.latency_ms === null ? "—" : `${provider.latency_ms}ms`}</strong></div><button className="provider-verify" type="button" onClick={onVerify} disabled={verifying || !provider.implementation} aria-label={`Verify ${provider.provider_name}`}>{verifying ? "Checking…" : "Verify"}</button><details className="provider-details"><summary>Details</summary><div><div><span>Limitations</span><p>{provider.limitations.length ? provider.limitations.join(" ") : "No limitations reported."}</p></div><div><span>Last result</span><p>{provider.last_verification_result.replaceAll("_", " ")}{provider.last_error_type ? ` · ${provider.last_error_type}` : ""}</p></div><div><span>Idempotency</span><p>{provider.idempotency_status ?? "Not reported"}</p></div></div></details></article>;
}
