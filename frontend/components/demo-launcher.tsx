"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRightIcon, FlaskIcon } from "./icons";
import { api, ApiError } from "../lib/api";
import { Button } from "./shell";

const failureReasons = ["expired_method", "insufficient_funds", "technical_degradation", "issuer_decline", "abandonment", "other"];

export function DemoLauncher() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ failureReason: "expired_method", amountPaise: "125000", paymentMethod: "card", incidentFlag: false });

  const update = (field: string, value: string | boolean) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const result = await api.runRecoveryDemo({
        external_event_id: `frontend-demo-${Date.now()}`,
        payment_id: `demo-payment-${Date.now()}`,
        customer_id: `synthetic-customer-${Date.now()}`,
        amount_paise: Number.parseInt(form.amountPaise, 10),
        currency: "INR",
        failure_reason: form.failureReason,
        incident_flag: form.incidentFlag,
        payment_method: form.paymentMethod as "card" | "upi" | "netbanking",
        decision_timestamp: new Date().toISOString(),
      });
      router.push(`/cases/${result.case_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The recovery demo could not be started.");
    } finally {
      setBusy(false);
    }
  };

  return <section className={`demo-launcher ${open ? "open" : ""}`}>
    <div className="demo-launcher-intro"><div className="demo-launcher-icon"><FlaskIcon size={19} /></div><div><strong>Run a real recovery journey</strong><p>Use synthetic observable input to create a case, decision, intervention, and persisted audit trail.</p></div><Button kind="secondary" onClick={() => setOpen((value) => !value)}>{open ? "Close" : "Run recovery demo"}<ArrowRightIcon size={15} /></Button></div>
    {open && <form className="demo-form" onSubmit={submit}><label><span>Failure reason</span><select value={form.failureReason} onChange={(event) => update("failureReason", event.target.value)}>{failureReasons.map((reason) => <option key={reason} value={reason}>{reason.replaceAll("_", " ")}</option>)}</select></label><label><span>Amount (paise)</span><input value={form.amountPaise} inputMode="numeric" pattern="[0-9]+" onChange={(event) => update("amountPaise", event.target.value)} required /></label><label><span>Payment method</span><select value={form.paymentMethod} onChange={(event) => update("paymentMethod", event.target.value)}><option value="card">Card</option><option value="upi">UPI</option><option value="netbanking">Netbanking</option></select></label><label className="demo-checkbox"><input type="checkbox" checked={form.incidentFlag} onChange={(event) => update("incidentFlag", event.target.checked)} /><span>Incident signal observed</span></label><Button type="submit" disabled={busy}>{busy ? "Starting…" : "Create synthetic case"}<ArrowRightIcon size={15} /></Button>{error && <p className="demo-error">{error}</p>}</form>}
  </section>;
}
