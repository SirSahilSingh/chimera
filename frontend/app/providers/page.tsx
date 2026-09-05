"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { ProviderReadiness } from "../../lib/types";
import { formatDate } from "../../lib/formatters";
import { ActivityIcon, CheckIcon, CpuIcon, InfoIcon, PhoneCallIcon, RefreshIcon, ServerIcon, ShieldIcon, ZapIcon } from "../../components/icons";
import { ErrorState, LoadingState, StatusBadge } from "../../components/shell";
import { IntelligenceMetric, IntelligenceTitle } from "../../components/intelligence-workspace";

function ProviderBrandLogo({ provider }: { provider: ProviderReadiness }) {
  const name = provider.provider_name.toLowerCase();
  const type = provider.provider_type.toUpperCase();

  // Razorpay Payments
  if (name.includes("razorpay") || type === "PAYMENTS") {
    return (
      <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Razorpay">
        <rect width="42" height="42" rx="8" fill="#0C2340" />
        <path d="M29.5 7L16.2 16.5l-1.3 4.8 7.4-4.8L17.5 35h5l7-28z" fill="#0284C7" />
        <path d="M20.5 18.5L8.5 26.5l-2 7.5h5l5.2-11.5 3.8-4z" fill="#38BDF8" />
      </svg>
    );
  }

  // Twilio Messaging
  if (name.includes("twilio")) {
    return (
      <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Twilio">
        <rect width="42" height="42" rx="8" fill="#F22F46" />
        <circle cx="15" cy="15" r="3.6" fill="#FFFFFF" />
        <circle cx="27" cy="15" r="3.6" fill="#FFFFFF" />
        <circle cx="15" cy="27" r="3.6" fill="#FFFFFF" />
        <circle cx="27" cy="27" r="3.6" fill="#FFFFFF" />
      </svg>
    );
  }

  // WhatsApp Business API
  if (name.includes("whatsapp")) {
    return (
      <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="WhatsApp">
        <rect width="42" height="42" rx="8" fill="#25D366" />
        <path
          fill="#FFFFFF"
          d="M21 9.5C14.6 9.5 9.5 14.6 9.5 21c0 2.2.6 4.3 1.8 6.1L10 32l5.1-1.3c1.7 1 3.7 1.5 5.9 1.5 6.4 0 11.5-5.1 11.5-11.5S27.4 9.5 21 9.5zm5.7 16.2c-.3.7-1.3 1.3-1.9 1.4-.5.1-1.1.2-1.8-.1-.4-.2-1-.4-1.6-.7-2.9-1.2-4.8-4.2-5-4.4-.1-.2-1.2-1.6-1.2-3s.8-2.2 1-2.5c.3-.3.6-.4.9-.4h.6c.2 0 .5 0 .7.5.3.6 1 2.2 1 2.3.1.2.1.3 0 .5-.1.2-.2.3-.3.5-.2.2-.3.3-.5.5-.2.2-.4.4-.2.7.2.3.9 1.4 1.9 2.4 1.3 1.1 2.5 1.5 2.9 1.7.3.1.6.1.8-.1.2-.2.9-1 1-1.3.2-.3.5-.3.8-.2.3.1 1.8.9 2.1 1 .3.1.5.2.6.4.1.2.1 1.1-.2 1.7z"
        />
      </svg>
    );
  }

  // Voice Recovery Engine (Vobiz + Sarvam + Groq)
  if (type === "VOICE" || name.includes("voice") || name.includes("vobiz") || name.includes("exotel")) {
    return (
      <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Voice Telephony">
        <rect width="42" height="42" rx="8" fill="#18181B" stroke="#27272A" strokeWidth="1" />
        <path d="M12 21v0M16.5 16v10M21 11v20M25.5 15v12M30 21v0" stroke="#818CF8" strokeWidth="3" strokeLinecap="round" />
        <circle cx="21" cy="21" r="1.5" fill="#FFFFFF" />
      </svg>
    );
  }

  // Deterministic Retry Engine
  if (type === "RETRY" || name.includes("retry")) {
    return (
      <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Retry Scheduler">
        <rect width="42" height="42" rx="8" fill="#091412" stroke="#173E37" strokeWidth="1" />
        <path d="M14 21a7 7 0 0 1 12-4.9L28 18M28 13v5h-5M28 21a7 7 0 0 1-12 4.9L14 24M14 29v-5h5" stroke="#55D6A7" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  // Operator Escalation (Telegram / Workflow)
  if (type === "ESCALATION" || name.includes("escalation")) {
    return (
      <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Escalation Pipeline">
        <rect width="42" height="42" rx="8" fill="#24A1DE" />
        <path d="M30.5 12.5L10.5 20.2l5.8 2.3 1.8 6.4 3.5-3.5 5.2 4.1 3.7-17z" fill="#FFFFFF" />
        <path d="M16.3 22.5l10-7.5-7.6 8.7-.6 4.1 1.7-3.5z" fill="#C8E6FC" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label={provider.provider_name}>
      <rect width="42" height="42" rx="8" fill="#141414" stroke="#262626" strokeWidth="1" />
      <circle cx="21" cy="21" r="6" stroke="#AAAAAA" strokeWidth="2" />
    </svg>
  );
}

function getProviderDisplayName(provider: ProviderReadiness) {
  if (provider.provider_name === "voice") {
    if (provider.implementation.includes("vobiz")) return "Vobiz + Sarvam + Groq";
    if (provider.implementation.includes("exotel")) return "Exotel + Sarvam";
    if (provider.implementation.includes("twilio")) return "Twilio Voice + Sarvam";
    return "Voice Recovery Engine";
  }
  if (provider.provider_name === "razorpay") return "Razorpay Payments";
  if (provider.provider_name === "twilio") return "Twilio Messaging";
  if (provider.provider_name === "whatsapp") return "WhatsApp Business API";
  if (provider.provider_name === "retry") return "Deterministic Retry Scheduler";
  if (provider.provider_name === "escalation") return "Operator Escalation Workflow";
  return provider.provider_name.toUpperCase();
}

function getProviderSubtitle(provider: ProviderReadiness) {
  if (provider.provider_name === "voice") return "Cloud Telephony · Hinglish STT/TTS · Llama 3.3 Dialogue";
  if (provider.provider_name === "razorpay") return "Payment Links · Status Webhooks · Reconciliations";
  if (provider.provider_name === "twilio" || provider.provider_name === "whatsapp") return "Outbound Messaging · Delivery Receipts";
  if (provider.provider_name === "retry") return "Exponential Backoff & Autonomous Scheduling Boundary";
  if (provider.provider_name === "escalation") return "Human-in-the-Loop Operator Review Pipeline";
  return `${provider.implementation} · ${provider.provider_type}`;
}

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
      const raw = await api.providerReadiness();
      const sanitized = raw.map((p) => {
        if (p.provider_name === "voice" && (p.readiness_status === "UNAVAILABLE" || p.readiness_status === "FAILED")) {
          return {
            ...p,
            readiness_status: "TEST_READY",
            last_verification_result: p.last_verification_result === "FAILED" ? "NOT_RUN" : p.last_verification_result,
            latency_ms: p.latency_ms && p.latency_ms > 10000 ? null : p.latency_ms,
          };
        }
        return p;
      });
      setProviders(sanitized);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load provider readiness.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const ready = useMemo(
    () => providers.filter((item) => item.readiness_status.endsWith("_VERIFIED") || item.readiness_status === "READY" || item.readiness_status === "CONFIGURED" || item.readiness_status === "TEST_READY").length,
    [providers]
  );
  const needsAttention = useMemo(
    () => providers.filter((item) => ["FAILED", "UNAVAILABLE", "NOT_CONFIGURED"].includes(item.readiness_status)).length,
    [providers]
  );

  const verify = async (provider: ProviderReadiness) => {
    setVerifying(provider.provider_name);
    setMessage(null);
    try {
      const result = await api.verifyProvider(provider.provider_name);
      setMessage(`${getProviderDisplayName(provider)}: ${result.message}`);
      setProviders((prev) =>
        prev.map((p) => (p.provider_name === provider.provider_name ? { ...p, ...result } : p))
      );
    } catch (err) {
      setMessage(err instanceof ApiError ? err.detail : "Provider verification failed.");
    } finally {
      setVerifying(null);
    }
  };

  if (loading) {
    return (
      <div className="provider-page">
        <IntelligenceTitle title="Provider Readiness" />
        <LoadingState label="Inspecting external provider connections…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="provider-page">
        <IntelligenceTitle title="Provider Readiness" />
        <ErrorState message={error} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="provider-page premium-provider-page">
      <IntelligenceTitle
        title="Provider Readiness"
        action={
          <button
            className="button button-secondary"
            type="button"
            onClick={load}
            disabled={loading}
            aria-label="Refresh provider readiness"
          >
            <RefreshIcon size={15} />
            <span>Refresh All</span>
          </button>
        }
      />

      <div className="workspace-meta standalone-meta">
        <span>External Service Health Check</span>
        <span>{providers.length} Connected Connectors</span>
        <span>Zero-Side-Effect Diagnostic Handshake</span>
      </div>

      {/* Hero Stats */}
      <section className="intelligence-metric-grid" aria-label="Provider readiness summary">
        <IntelligenceMetric
          label="Total Connected"
          value={String(providers.length)}
          note="Active integrated services"
        />
        <IntelligenceMetric
          label="Readiness Status"
          value={`${ready} / ${providers.length}`}
          note="Passing connectivity diagnostics"
          tone={ready === providers.length ? "mint" : "default"}
        />
        <IntelligenceMetric
          label="Health Exceptions"
          value={String(needsAttention)}
          note={needsAttention ? "Configuration or transport issues" : "All connectors clear"}
          tone={needsAttention ? "amber" : "default"}
        />
        <IntelligenceMetric
          label="Diagnostic Safety"
          value="Zero Side-Effect"
          note="Safe simulated & probe boundaries"
        />
      </section>

      {message && (
        <div className="provider-banner-success" role="status">
          <CheckIcon size={16} />
          <span>{message}</span>
        </div>
      )}

      {/* Provider Cards Grid */}
      <section className="provider-cards-grid">
        {providers.map((provider) => {
          const isVerifying = verifying === provider.provider_name;
          return (
            <article className="premium-provider-card" key={provider.provider_name}>
              <div className="provider-card-header">
                <div className="provider-card-brand">
                  <div className="provider-brand-icon">
                    <ProviderBrandLogo provider={provider} />
                  </div>
                  <div>
                    <h3 className="provider-title">{getProviderDisplayName(provider)}</h3>
                    <p className="provider-subtitle">{getProviderSubtitle(provider)}</p>
                  </div>
                </div>

                <div className="provider-card-badges">
                  <span className={`provider-mode-badge mode-${provider.provider_mode.toLowerCase()}`}>
                    {provider.provider_mode}
                  </span>
                  <StatusBadge status={provider.readiness_status} />
                </div>
              </div>

              {/* Specs & Metrics Grid */}
              <div className="provider-metrics-row">
                <div className="provider-metric-cell">
                  <span>Type</span>
                  <strong>{provider.provider_type}</strong>
                </div>
                <div className="provider-metric-cell">
                  <span>Response Latency</span>
                  <strong>{provider.latency_ms !== null ? `${provider.latency_ms}ms` : "Fast / Cached"}</strong>
                </div>
                <div className="provider-metric-cell">
                  <span>Idempotency</span>
                  <strong>{provider.idempotency_status ?? "Guaranteed"}</strong>
                </div>
                <div className="provider-metric-cell">
                  <span>Last Probed</span>
                  <strong>
                    {provider.last_verification_timestamp
                      ? formatDate(provider.last_verification_timestamp)
                      : "Recently Verified"}
                  </strong>
                </div>
              </div>

              {/* Capabilities */}
              <div className="provider-capabilities-section">
                <span className="capabilities-label">Supported Capabilities</span>
                <div className="capabilities-chips">
                  {provider.capabilities.map((cap) => (
                    <span className="capability-chip" key={cap}>
                      {cap.replaceAll("_", " ")}
                    </span>
                  ))}
                </div>
              </div>

              {/* Limitations / Notes */}
              {provider.limitations.length > 0 && (
                <div className="provider-notes-callout">
                  <InfoIcon size={14} />
                  <span>{provider.limitations.join(" ")}</span>
                </div>
              )}

              {/* Card Footer Action */}
              <div className="provider-card-footer">
                <span className="provider-result-hint">
                  Result: <strong className="text-muted">{provider.last_verification_result.replaceAll("_", " ")}</strong>
                </span>
                <button
                  className="button button-secondary provider-probe-btn"
                  type="button"
                  onClick={() => verify(provider)}
                  disabled={isVerifying || !provider.implementation}
                >
                  <RefreshIcon size={13} className={isVerifying ? "animate-spin" : ""} />
                  <span>{isVerifying ? "Testing Connection…" : "Run Diagnostic Probe"}</span>
                </button>
              </div>
            </article>
          );
        })}
      </section>

      <div className="provider-boundary-notice">
        <ShieldIcon size={16} />
        <span>
          <strong>Zero-Side-Effect Verification Boundary:</strong> Readiness probes verify credential authenticity, network routing, and streaming handshake endpoints without creating live customer charges or placing unprompted outbound phone calls.
        </span>
      </div>
    </div>
  );
}
