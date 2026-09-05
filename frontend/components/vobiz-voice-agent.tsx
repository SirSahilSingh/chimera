"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowRightIcon, CheckIcon, CopyIcon, PhoneCallIcon, RefreshIcon } from "./icons";
import { api, ApiError } from "../lib/api";
import { formatFailureReason, formatPaise } from "../lib/formatters";
import type { VoiceTurn } from "../lib/types";

type CallStatus = "idle" | "dialing" | "ringing" | "in_call" | "completed" | "failed";

function statusBadge(status: CallStatus) {
  switch (status) {
    case "dialing":
      return { label: "Dialing...", className: "connecting" };
    case "ringing":
      return { label: "Phone Ringing...", className: "speaking" };
    case "in_call":
      return { label: "In Call · Agent speaking", className: "listening" };
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
  const [phoneDigits, setPhoneDigits] = useState(() => {
    const digits = (initialPhone || "+919876543210").replace(/\D/g, "");
    return digits.startsWith("91") ? digits.slice(2, 12) : digits.slice(-10);
  });
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
    if (!/^\d{10}$/.test(phoneDigits)) {
      setErrorMessage("Please enter a valid 10-digit Indian mobile number.");
      return;
    }
    const cleanPhone = `+91${phoneDigits}`;

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
          <span className="section-overline">LIVE OUTBOUND TELEPHONY</span>
          <h2 id="vobiz-voice-agent-title">Live Hinglish Voice Recovery Call</h2>
          <p>
            CHIMERA dials your mobile phone, understands spoken Hinglish, and responds with the next safe recovery step.
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
          <div className="voice-telephony-trigger-card">
            <div className="voice-trigger-head">
              <span className="section-overline">TELEPHONY TRIGGER</span>
              <h3>Destination Phone</h3>
              <p>Enter your mobile number to receive the live demo call</p>
            </div>

            <form className="voice-trigger-form" onSubmit={handleStartCall}>
              <div className="voice-phone-input-wrap">
                <span className="phone-prefix">+91</span>
                <input
                  id="target-phone-input"
                  type="tel"
                  value={phoneDigits}
                  onChange={(e) => setPhoneDigits(e.target.value.replace(/\D/g, "").slice(0, 10))}
                  placeholder="9876543210"
                  inputMode="numeric"
                  minLength={10}
                  maxLength={10}
                  pattern="[0-9]{10}"
                  aria-label="10-digit Indian mobile number"
                  disabled={isCalling}
                />
              </div>
              <button
                className="button button-primary voice-call-action-btn"
                type="submit"
                disabled={isCalling}
              >
                <PhoneCallIcon size={15} />
                <span>{isCalling ? "Calling Your Phone…" : "Call My Phone"}</span>
              </button>
            </form>
          </div>

          {errorMessage && (
            <div className="voice-agent-error" role="alert">
              <span>
                <strong>Call Dispatch Notice: </strong>
                {errorMessage}
              </span>
              <button className="button button-secondary" type="button" onClick={() => handleStartCall()}>
                Try again <ArrowRightIcon size={14} />
              </button>
            </div>
          )}

          <div className="voice-agent-section-head">
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
                  Click <strong>&quot;Call My Phone&quot;</strong> above. Answer the incoming phone call and speak in Hinglish (e.g. &quot;payment link bhej do&quot; or &quot;kyun fail hua?&quot;).
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
                <span>{t.speaker === "agent" ? "CHIMERA AGENT" : "YOU (Hinglish)"}</span>
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
      </div>
    </section>
  );
}
