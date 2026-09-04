"use client";

import Link from "next/link";
import { ArrowRightIcon } from "../../components/icons";
import { InitialCheckout } from "../../components/initial-checkout";

export default function CheckoutPage() {
  return <div className="checkout-page checkout-surface">
    <div className="checkout-topline"><div><span className="checkout-kicker">Evaluation Lab <i /> Razorpay test</span><h1>Start a real payment test</h1><p>Open a Razorpay test checkout with a stored amount and customer number. CHIMERA creates a recovery case only after a signed failure webhook.</p></div><Link href="/demo" className="checkout-back">Back to Demo Scenarios <ArrowRightIcon size={14} /></Link></div>
    <InitialCheckout />
  </div>;
}
