"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRightIcon, CheckIcon, FlaskIcon, ShieldIcon } from "../../components/icons";
import { IntelligenceTitle } from "../../components/intelligence-workspace";

const scenarios = [
  { value: "payment_recovery", label: "Payment Recovery", summary: "Razorpay TEST → recovery case", setup: "Create a real test payment, fail it, and inspect the recovery response.", evidence: "Provider event, decision, recovery action, and outcome state", icon: ShieldIcon },
  { value: "voice_recovery", label: "Voice-Assisted Recovery", summary: "Live Hinglish outbound phone call", setup: "An abandoned payment recovered through a live Hinglish phone call.", evidence: "Live transcript, telephony stream, and persisted recovery evidence", icon: FlaskIcon },
] as const;

type ScenarioValue = (typeof scenarios)[number]["value"];

export default function DemoScenariosPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<ScenarioValue>("payment_recovery");
  const selectedScenario = scenarios.find((scenario) => scenario.value === selected) ?? scenarios[0];

  const launch = () => {
    router.push(selected === "payment_recovery" ? "/checkout" : "/voice-recovery");
  };

  return <div className="evaluation-page">
    <IntelligenceTitle title="Demo Scenarios" />
    <section className="scenario-grid" aria-label="Demo scenarios">{scenarios.map((scenario) => { const Icon = scenario.icon; return <button type="button" className={`scenario-card ${selected === scenario.value ? "selected" : ""}`} onClick={() => setSelected(scenario.value)} key={scenario.value}><div className="scenario-card-head"><span className="scenario-icon"><Icon size={17} /></span>{selected === scenario.value && <span className="scenario-selected"><CheckIcon size={13} />Selected</span>}</div><strong>{scenario.label}</strong><span>{scenario.summary}</span><small>{scenario.setup}</small><em>{scenario.evidence}</em></button>; })}</section>

    <section className="scenario-setup"><div><h2>{selectedScenario.label}</h2><p>{selectedScenario.setup}</p></div><div className="scenario-setup-actions"><button className="button button-primary" type="button" onClick={launch}>{selected === "payment_recovery" ? "Open Razorpay test" : "Open voice recovery"}<ArrowRightIcon size={15} /></button></div></section>
  </div>;
}
