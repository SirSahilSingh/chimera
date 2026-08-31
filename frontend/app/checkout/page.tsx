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
        theme: { color: "#55d6a7" },
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

  return <div className="overview-page checkout-page">
    <div className="overview-toolbar"><div className="overview-toolbar-left"><h1>Initial checkout</h1></div><Link href="/" className="overview-button overview-button-light">Back to overview</Link></div>
    <section className="overview-feature checkout-card">
      <div className="overview-feature-head"><h2>Run a real Razorpay checkout</h2><ShieldIcon size={18} /></div>
      <p className="checkout-copy">This creates a Razorpay Order. A failed attempt becomes a CHIMERA recovery case only after Razorpay delivers the signed payment.failed webhook.</p>
      <form className="checkout-form" onSubmit={startCheckout}>
        <label>Amount in INR<input inputMode="decimal" min="1" step="1" value={amount} onChange={(event) => setAmount(event.target.value)} required /></label>
        <label>Customer phone<input inputMode="tel" placeholder="+91XXXXXXXXXX" value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
        <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Creating order…" : "Open Razorpay Checkout"}<ArrowRightIcon size={15} /></button>
      </form>
      {message && <div className="queue-notice" role="status"><CheckIcon size={15} /><span>{message}</span></div>}
      {error && <div className="state-panel error-state"><span>{error}</span></div>}
      {order && <div className="checkout-order"><span>Order created</span><strong>{order.provider_order_id}</strong><small>{order.status} · {order.provider_mode} · {order.amount_paise / 100} INR</small></div>}
    </section>
  </div>;
}
