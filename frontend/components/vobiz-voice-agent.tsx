"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowRightIcon, CheckIcon, CopyIcon, PhoneCallIcon, RefreshIcon, ShieldIcon } from "./icons";
import { api, ApiError } from "../lib/api";
import { formatFailureReason, formatPaise } from "../lib/formatters";
import type { VoiceTurn } from "../lib/types";

type CallStatus = "idle" | "dialing" | "ringing" | "in_call" | "completed" | "failed";

function statusBadge(status: CallStatus) {
  switch (status) {
    case "dialing":
      return { label: "Dialing via Vobiz...", className: "connecting" };
    case "ringing":
      return { label: "Phone Ringing...", className: "speaking" };
    case "in_call":
      return { label: "In Call · Sarvam AI Speaking", className: "listening" };
    case "completed":
      return { label: "Call Completed", className: "completed" };
    case "failed":
      return { label: "Call Needs Attention", className: "error" };
    default:
      return { label: "Ready for Live Call", className: "idle" };
  }
}

export function VobizVoiceAgent({
  interventionId,
  amountPaise,
  failureReason,
  paymentMethod,
  initialPhone = "+919876543210",
}: {
  interventionId: string;
  amountPaise: number;
  failureReason: string;
  paymentMethod: string;
  initialPhone?: string | null;
}) {
  const [phoneNumber, setPhoneNumber] = useState(initialPhone || "+919876543210");
  const [callStatus, setCallStatus] = useState<CallStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [turns, setTurns] = useState<VoiceTurn[]>([]);
  const [paymentLink, setPaymentLink] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const pollHistory = async () => {
    try {
      const history = await api.getVoiceHistory(interventionId);
      if (history && history.call) {
        const rawStatus = (history.call.status || "").toLowerCase();
        if (
          rawStatus.includes("completed") ||
          rawStatus.includes("declined") ||
          rawStatus.includes("cancelled")
        ) {
          setCallStatus("completed");
          stopPolling();
        } else if (rawStatus.includes("failed") || rawStatus.includes("no_answer")) {
          setCallStatus("failed");
          if (history.call.failure_reason) {
            setErrorMessage(history.call.failure_reason);
          }
          stopPolling();
        } else if (
          rawStatus.includes("connect") ||
          rawStatus.includes("conversation") ||
          rawStatus.includes("resolution")
        ) {
          setCallStatus("in_call");
        } else if (rawStatus.includes("ring")) {
          setCallStatus("ringing");
        }

        if (history.turns && history.turns.length > 0) {
          setTurns(history.turns);
        }

        // Look for payment link either directly on call record or in attached events
        if (history.call.payment_link) {
          setPaymentLink(history.call.payment_link);
        } else {
          const paymentEvent = history.events?.find(
            (e) => e.event_type === "PAYMENT_LINK_ATTACHED" || Boolean(e.payload?.payment_link)
          );
          if (paymentEvent?.payload?.payment_link) {
            setPaymentLink(String(paymentEvent.payload.payment_link));
          }
        }
      }
    } catch {
      // Ignore background poll errors
    }
  };

  const handleStartCall = async (e?: FormEvent) => {
    if (e) e.preventDefault();
    const cleanPhone = phoneNumber.trim();
    if (!cleanPhone || cleanPhone.length < 8) {
      setErrorMessage("Please enter a valid phone number (e.g. +919876543210)");
      return;
    }

    setErrorMessage(null);
    setCallStatus("dialing");
    setTurns([]);
    setPaymentLink(null);

    try {
      await api.startOutboundCall({
        intervention_id: interventionId,
        customer_phone: cleanPhone,
      });

      // Start polling for live call progress and turns
      stopPolling();
      pollingRef.current = setInterval(pollHistory, 1000);
      void pollHistory();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "Failed to initiate outbound call.";
      setErrorMessage(detail);
      setCallStatus("failed");
      stopPolling();
    }
  };

  const handleCopyLink = () => {
    if (!paymentLink) return;
    navigator.clipboard.writeText(paymentLink);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);

  const badge = statusBadge(callStatus);
  const isCalling = callStatus === "dialing" || callStatus === "ringing" || callStatus === "in_call";

  return (
    <section className="voice-agent-demo" aria-labelledby="vobiz-voice-agent-title">
      <div className="voice-agent-head">
        <div>
          <span className="section-overline">LIVE OUTBOUND TELEPHONY · VOBIZ + SARVAM</span>
          <h2 id="vobiz-voice-agent-title">Live Hinglish Voice Recovery Call</h2>
          <p>
            Vobiz dials your mobile phone, Sarvam Saaras transcribes spoken Hinglish, Groq reasons in 150ms, and Sarvam Bulbul speaks the recovery response.
          </p>
        </div>
        <span className={`voice-agent-status ${badge.className}`}>
          <span className="voice-agent-status-dot" />
          {badge.label}
        </span>
      </div>

      <div className="voice-agent-case" aria-label="Payment context">
        <div>
          <span>Amount at risk</span>
          <strong>{formatPaise(amountPaise)}</strong>
        </div>
        <div>
          <span>Failure reason</span>
          <strong>{formatFailureReason(failureReason)}</strong>
        </div>
        <div>
          <span>Payment method</span>
          <strong>{paymentMethod}</strong>
        </div>
      </div>

      <div className="voice-agent-body">
        <div className="voice-agent-conversation">
          <div className="voice-agent-section-head">
            <div>
              <span className="section-overline">TELEPHONY TRIGGER</span>
              <strong>Destination Phone</strong>
            </div>
            <small>Enter your mobile number to receive the live demo call</small>
          </div>

          <form className="voice-agent-text-form" onSubmit={handleStartCall} style={{ marginTop: 0 }}>
            <div style={{ display: "flex", gap: "0.75rem", width: "100%" }}>
              <input
                id="target-phone-input"
                type="tel"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+919876543210"
                disabled={isCalling}
                style={{
                  fontFamily: "monospace",
                  fontSize: "1rem",
                  flex: 1,
                  padding: "0.6rem 0.85rem",
                  borderRadius: "6px",
                  border: "1px solid var(--border, #333)",
                  background: "var(--surface-input, rgba(255,255,255,0.04))",
                  color: "inherit",
                }}
              />
              <button
                className="button button-primary"
                type="submit"
                disabled={isCalling}
                style={{ whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: "0.5rem" }}
              >
                <PhoneCallIcon size={16} />
                {isCalling ? "Call in Progress..." : "Call My Phone via Vobiz"}
              </button>
            </div>
          </form>

          {errorMessage && (
            <div className="voice-agent-error" role="alert" style={{ marginTop: "1rem" }}>
              <span>
                <strong>Call Dispatch Notice: </strong>
                {errorMessage}
              </span>
              <button className="button button-secondary" type="button" onClick={() => handleStartCall()}>
                Try again <ArrowRightIcon size={14} />
              </button>
            </div>
          )}

          <div className="voice-agent-section-head" style={{ marginTop: "1.5rem" }}>
            <div>
              <span className="section-overline">LIVE CALL TRANSCRIPT</span>
              <strong>Conversation Turns</strong>
            </div>
            {isCalling && (
              <small style={{ color: "var(--accent, #60a5fa)", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                <RefreshIcon size={12} className="spin" /> Listening in real time...
              </small>
            )}
          </div>

          <div className="voice-agent-transcript" role="log" aria-live="polite" style={{ minHeight: "180px" }}>
            {turns.length === 0 && !isCalling && (
              <div className="voice-agent-empty">
                <PhoneCallIcon size={20} />
                <span>
                  Click <strong>&quot;Call My Phone via Vobiz&quot;</strong> above. Answer the incoming phone call and speak in Hinglish (e.g. &quot;payment link bhej do&quot; or &quot;kyun fail hua?&quot;).
                </span>
              </div>
            )}
            {turns.length === 0 && isCalling && (
              <div className="voice-agent-empty">
                <PhoneCallIcon size={20} />
                <span>Connecting call to your phone... Transcript will appear live here as you speak.</span>
              </div>
            )}
            {turns.map((t, idx) => (
              <div className={`voice-agent-line ${t.speaker === "agent" ? "agent" : "customer"}`} key={t.id || idx}>
                <span>{t.speaker === "agent" ? "CHIMERA AI (Sarvam + Groq)" : "YOU (Hinglish)"}</span>
                <p>{t.text}</p>
                {t.intent && (
                  <small style={{ opacity: 0.7, fontSize: "0.75rem", display: "inline-block", marginTop: "2px" }}>
                    Intent: {t.intent}
                  </small>
                )}
              </div>
            ))}
          </div>

          {paymentLink && (
            <div
              style={{
                marginTop: "1rem",
                padding: "0.85rem 1rem",
                borderRadius: "8px",
                border: "1px solid rgba(52, 211, 153, 0.4)",
                background: "rgba(16, 185, 129, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "1rem",
              }}
            >
              <div>
                <strong style={{ display: "block", color: "#34d399", fontSize: "0.9rem" }}>
                  <CheckIcon size={14} style={{ display: "inline", marginRight: "4px" }} />
                  Payment Link Dispatched
                </strong>
                <span style={{ fontSize: "0.8rem", opacity: 0.85, wordBreak: "break-all" }}>{paymentLink}</span>
              </div>
              <button
                className="button button-secondary"
                type="button"
                onClick={handleCopyLink}
                style={{ padding: "0.4rem 0.75rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.35rem" }}
              >
                <CopyIcon size={13} /> {copiedLink ? "Copied!" : "Copy Link"}
              </button>
            </div>
          )}
        </div>

        <aside className="voice-agent-guardrail">
          <div className="voice-agent-guardrail-head">
            <ShieldIcon size={17} />
            <span>Telephony Stack</span>
          </div>
          <h3>Direct Outbound PSTN</h3>
          <p>
            Unlike browser microphone demos, this dials a real phone on Indian telecom networks via Vobiz, passing audio directly to Sarvam.
          </p>
          <div className="voice-agent-guardrail-list">
            <span>
              <CheckIcon size={13} /> Vobiz Indian Cloud Telephony
            </span>
            <span>
              <CheckIcon size={13} /> Sarvam Saaras v3 STT (Hinglish)
            </span>
            <span>
              <CheckIcon size={13} /> Groq Llama 3.3 (~150ms TTFT)
            </span>
            <span>
              <CheckIcon size={13} /> Sarvam Bulbul v3 TTS (Shubh)
            </span>
            <span>
              <CheckIcon size={13} /> Zero credential leakage
            </span>
          </div>
        </aside>
      </div>
    </section>
  );
}
