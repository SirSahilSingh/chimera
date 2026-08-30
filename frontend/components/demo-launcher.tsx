"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRightIcon, FlaskIcon } from "./icons";
import { api, ApiError } from "../lib/api";
import { Button } from "./shell";

const scenarios = [
  { value: "payment_recovery", label: "Expired method → payment link", note: "Creates, confirms, and records a local payment." },
  { value: "technical_retry", label: "Technical degradation → retry later", note: "Schedules the stored retry without contacting a customer." },
  { value: "voice_recovery", label: "Voice recovery → customer requests link", note: "Runs the Demo Voice Agent, then confirms the link." },
  { value: "escalation", label: "Escalation → human review", note: "Opens a real operator review record." },
] as const;

export function DemoLauncher() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<number | null>(null);
  const [scenario, setScenario] = useState<(typeof scenarios)[number]["value"]>("payment_recovery");
  const selected = scenarios.find((item) => item.value === scenario) ?? scenarios[0];

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.runDemo({ scenario, provider_mode: "LOCAL" });
      for (const index of [0, 1, 2, 3, 4]) {
        setStage(index);
        await new Promise((resolve) => window.setTimeout(resolve, 500));
      }
      router.push(`/cases/${result.case_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The recovery demo could not be started.");
    } finally {
      setBusy(false);
      setStage(null);
    }
  };

  return <section className={`demo-launcher ${open ? "open" : ""}`}>
    <div className="demo-launcher-intro"><div className="demo-launcher-icon"><FlaskIcon size={19} /></div><div><strong>Run a real recovery journey</strong><p>Launch one of four synthetic scenarios through the persisted decision and provider boundaries.</p></div><Button kind="secondary" onClick={() => setOpen((value) => !value)}>{open ? "Close" : "Run recovery demo"}<ArrowRightIcon size={15} /></Button></div>
    {open && <form className="demo-form" onSubmit={submit}>
      <label><span>Scenario</span><select value={scenario} onChange={(event) => setScenario(event.target.value as typeof scenario)}>{scenarios.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><small>{selected.note}</small></label>
      <label><span>Provider mode</span><select value="LOCAL" disabled><option value="LOCAL">LOCAL · Demo Provider Execution</option></select><small>Safe local mode; no external provider call is made.</small></label>
      <Button type="submit" disabled={busy}>{busy ? "Walking through recovery…" : "Launch scenario"}<ArrowRightIcon size={15} /></Button>
      {stage !== null && <div className="demo-stage-progress" aria-live="polite"><span>Live walkthrough</span><div>{["Detect", "Diagnose", "Decide", "Intervene", "Recover"].map((label, index) => <span className={index <= stage ? "complete" : ""} key={label}><i>{index < stage ? "✓" : index + 1}</i>{label}</span>)}</div></div>}
      {error && <p className="demo-error" role="alert">{error}</p>}
    </form>}
  </section>;
}
