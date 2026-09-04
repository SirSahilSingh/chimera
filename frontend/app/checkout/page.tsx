"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRightIcon, CheckIcon, ShieldIcon } from "../../components/icons";
import { ApiError, api } from "../../lib/api";
import type { PaymentOrder } from "../../lib/types";

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export default function CheckoutPage() {
  const [amount, setAmount] = useState("1000");
  const [phone, setPhone] = useState("");
  const [order, setOrder] = useState<PaymentOrder | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    document.body.appendChild(script);
    return () => script.remove();
  }, []);

  const startCheckout = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const nextOrder = await api.createPaymentOrder({
        external_reference_id: `checkout-${Date.now()}`,
        customer_id: phone || "checkout-customer",
        customer_phone: phone || undefined,
        amount_paise: Math.round(Number(amount) * 100),
        currency: "INR",
        description: "CHIMERA checkout test",
      });
      setOrder(nextOrder);
      if (!nextOrder.checkout_key_id) throw new Error("Razorpay Checkout key is not available from the backend.");
      if (!window.Razorpay) throw new Error("Razorpay Checkout is still loading. Try again in a moment.");
      const checkout = new window.Razorpay({
        key: nextOrder.checkout_key_id,
        amount: nextOrder.amount_paise,
        currency: nextOrder.currency,
        name: "CHIMERA",
        description: nextOrder.description,
        order_id: nextOrder.provider_order_id,
        prefill: { contact: nextOrder.customer_phone ?? undefined },
        theme: { color: "#46e083" },
        modal: { ondismiss: () => setMessage("Checkout closed. CHIMERA is waiting for the provider outcome.") },
      });
      checkout.open();
      setMessage("Checkout opened. CHIMERA will react only after the signed provider webhook arrives.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : err instanceof Error ? err.message : "Could not create the checkout order.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="checkout-page checkout-surface">
    <div className="checkout-topline"><div><span className="checkout-kicker">Evaluation Lab <i /> Razorpay test</span><h1>Start a real payment test</h1><p>Open a Razorpay test checkout with a stored amount and customer number. CHIMERA creates a recovery case only after a signed failure webhook.</p></div><Link href="/demo" className="checkout-back">Back to Demo Scenarios <ArrowRightIcon size={14} /></Link></div>
    <div className="checkout-layout">
      <section className="checkout-form-card"><div className="checkout-card-head"><div><span className="checkout-step">01 / Checkout details</span><h2>Set the test inputs</h2><p>Use test data only. No live charge is made from this workspace.</p></div><div className="checkout-card-icon"><ShieldIcon size={19} /></div></div><form className="checkout-form" onSubmit={startCheckout}><label>Amount in INR<input inputMode="decimal" min="1" step="1" value={amount} onChange={(event) => setAmount(event.target.value)} required /><small>The amount sent to Razorpay TEST.</small></label><label>Customer phone <span className="optional-label">Optional</span><input inputMode="tel" placeholder="+91XXXXXXXXXX" value={phone} onChange={(event) => setPhone(event.target.value)} /><small>Used as the customer reference for the test.</small></label><button className="button button-primary checkout-submit" type="submit" disabled={busy}>{busy ? "Creating order…" : "Open Razorpay Checkout"}<ArrowRightIcon size={15} /></button></form>{message && <div className="checkout-message" role="status"><CheckIcon size={15} /><span>{message}</span></div>}{error && <div className="checkout-error" role="alert">{error}</div>}{order && <div className="checkout-order"><div><span>Order created</span><strong>{order.provider_order_id}</strong></div><small>{order.status} · {order.provider_mode} · {order.amount_paise / 100} INR</small></div>}</section>
      <aside className="checkout-guide"><span className="checkout-step">02 / What happens next</span><h2>One test, three records.</h2><div className="checkout-guide-list"><div><b>01</b><div><strong>Create the order</strong><p>Razorpay returns a test order reference.</p></div></div><div><b>02</b><div><strong>Complete or fail checkout</strong><p>The provider remains the source of payment truth.</p></div></div><div><b>03</b><div><strong>Inspect the recovery case</strong><p>A signed failure webhook opens the path into Demo Scenarios and Decision Room.</p></div></div></div><div className="checkout-guide-note"><ShieldIcon size={15} /><span>CHIMERA does not infer a failure from the browser. It waits for the signed provider event.</span></div></aside>
    </div>
  </div>;
}
