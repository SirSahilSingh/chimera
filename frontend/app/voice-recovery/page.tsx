"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ArrowRightIcon, CheckIcon } from "../../components/icons";
import { BrowserVoiceAgent } from "../../components/browser-voice-agent";
import { DropdownField, ErrorState, LoadingState } from "../../components/shell";
import { IntelligenceTitle } from "../../components/intelligence-workspace";
import { ApiError, api } from "../../lib/api";
import type { DemoRunResponse, RecoveryJourney } from "../../lib/types";

const failureReasons = [
  ["insufficient_funds", "Insufficient funds"],
  ["issuer_decline", "Issuer decline"],
  ["expired_method", "Expired payment method"],
  ["technical_degradation", "Technical degradation"],
  ["abandonment", "Checkout abandoned"],
] as const;

const paymentMethods = [
  ["card", "Card"],
  ["upi", "UPI"],
  ["netbanking", "Net banking"],
] as const;

export default function VoiceRecoveryPage() {
  const [amount, setAmount] = useState("1250");
  const [failureReason, setFailureReason] = useState("insufficient_funds");
  const [paymentMethod, setPaymentMethod] = useState<"card" | "upi" | "netbanking">("card");
  const [phoneDigits, setPhoneDigits] = useState("");
  const [run, setRun] = useState<DemoRunResponse | null>(null);
  const [journey, setJourney] = useState<RecoveryJourney | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startRecovery = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError("Enter an amount greater than zero.");
      return;
    }
    if (!/^\d{10}$/.test(phoneDigits)) {
      setError("Enter a valid 10-digit Indian mobile number.");
      return;
    }

    setBusy(true);
    setError(null);
    setRun(null);
    setJourney(null);
    try {
      const result = await api.runDemo({
        scenario: "voice_recovery",
        provider_mode: "LOCAL",
        customer_phone: `+91${phoneDigits}`,
        amount_paise: Math.round(numericAmount * 100),
        failure_reason: failureReason,
        payment_method: paymentMethod,
      });
      const persistedJourney = await api.getJourney(result.case_id);
      setRun(result);
      setJourney(persistedJourney);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The voice recovery scenario could not be started.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="voice-recovery-page">
    <IntelligenceTitle title="Voice-Assisted Recovery" action={<Link className="button button-secondary" href="/demo">Back to Demo Scenarios <ArrowRightIcon size={14} /></Link>} />
    <section className="voice-context-card">
      <div className="voice-context-head"><div><span className="section-overline">01 / RECOVERY CONTEXT</span><h2>Set The Call Inputs</h2></div></div>
      <form className="voice-context-form" onSubmit={startRecovery}>
        <label><span className="field-label">Amount At Risk <span className="required-mark" aria-hidden="true">*</span></span><input inputMode="decimal" min="1" step="1" value={amount} onChange={(event) => setAmount(event.target.value)} required /><small>Amount the agent should refer to during the call.</small></label>
        <div className="voice-context-field"><DropdownField label="Failure Reason" required value={failureReason} onChange={setFailureReason} options={failureReasons.map(([value, label]) => ({ value, label }))} /></div>
        <div className="voice-context-field"><DropdownField label="Payment Method" required value={paymentMethod} onChange={(value) => setPaymentMethod(value as "card" | "upi" | "netbanking")} options={paymentMethods.map(([value, label]) => ({ value, label }))} /></div>
        <label><span className="field-label">Customer Phone <span className="required-mark" aria-hidden="true">*</span></span><div className="phone-field"><span className="phone-prefix">+91</span><input aria-label="10-digit Indian mobile number" inputMode="numeric" type="tel" placeholder="9876543210" value={phoneDigits} onChange={(event) => setPhoneDigits(event.target.value.replace(/\D/g, "").slice(0, 10))} minLength={10} maxLength={10} pattern="[0-9]{10}" required /></div><small>Enter exactly 10 digits. The call will be placed to this number.</small></label>
        <button className="button button-primary voice-context-submit" type="submit" disabled={busy}>{busy ? "Preparing recovery…" : "Start voice recovery"}<ArrowRightIcon size={15} /></button>
      </form>
    </section>

    {error && <ErrorState message={error} />}
    {busy && <div className="demo-monitor-loading"><LoadingState label="Creating the persisted recovery case" /></div>}
    {run && journey && !busy && <section className="voice-run-context"><div><span className="section-overline">02 / LIVE RECOVERY</span><h2>Call context saved</h2><p>Case {run.case_id.slice(0, 12)}… is ready. Use the call control below to reach the customer.</p></div><span className="voice-context-note"><CheckIcon size={14} /> Persisted</span></section>}
    {run && journey && !busy && <BrowserVoiceAgent interventionId={run.intervention_id} amountPaise={journey.case.amount_paise} failureReason={journey.case.failure_reason} paymentMethod={journey.case.payment_method} initialPhone={journey.case.customer_phone} />}
  </div>;
}
