"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckIcon, CopyIcon, InfoIcon, ShieldIcon } from "../../../components/icons";

const sectionNames: Record<string, string> = {
  general: "General",
  environments: "Environments",
  "provider-modes": "Provider Modes",
  "decision-policy": "Decision Policy",
  safety: "Safety",
  "audit-data": "Audit & Data",
};

export default function SettingsSectionPage({ params }: { params: { section: string } }) {
  const section = sectionNames[params.section] ? params.section : "general";
  const title = sectionNames[section];
  return <div className="settings-page"><div className="settings-page-head"><div><h1>{title}</h1><p>Workspace configuration for the CHIMERA recovery control plane.</p></div><span className="settings-demo-note">Demo workspace</span></div>{section === "general" && <GeneralSettings />}{section === "environments" && <EnvironmentSettings />}{section === "provider-modes" && <ProviderModeSettings />}{section === "decision-policy" && <DecisionPolicySettings />}{section === "safety" && <SafetySettings />}{section === "audit-data" && <AuditDataSettings />}</div>;
}

function GeneralSettings() {
  const [name, setName] = useState("CHIMERA");
  const [saved, setSaved] = useState(false);
  return <div className="settings-stack"><SettingsCard title="Workspace name" description="Used to identify this recovery workspace in the dashboard and audit records." footer={<SaveButton saved={saved} onClick={() => setSaved(true)} />}><div className="settings-input-row"><span>chimera.local/</span><input value={name} onChange={(event) => { setName(event.target.value); setSaved(false); }} aria-label="Workspace name" /></div></SettingsCard><SettingsCard title="Workspace identity" description="A compact identity for the operator workspace." footer={<span className="settings-muted">Synthetic environment</span>}><div className="workspace-identity"><span className="settings-identity-mark">C</span><div><strong>CHIMERA Recovery Agent</strong><span>Revenue recovery operations</span></div></div></SettingsCard><SettingsCard title="Workspace ID" description="Used when referring to this workspace in internal records." footer={<span className="settings-muted">Read-only</span>}><div className="settings-code-row"><code>ws_chimera_demo_01</code><button className="settings-icon-button" type="button" aria-label="Copy workspace ID"><CopyIcon size={15} /></button></div></SettingsCard><SettingsCard title="Workspace behavior" description="These defaults apply to this browser's demo workspace." footer={<SaveButton saved={saved} onClick={() => setSaved(true)} />}><ToggleRow label="Show synthetic data boundaries" detail="Keep Demo, Synthetic, and Local labels visible across the product." defaultChecked /><ToggleRow label="Remember the last workspace view" detail="Return to the last visited control-plane surface." defaultChecked /></SettingsCard></div>;
}

function EnvironmentSettings() {
  const [custom, setCustom] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const addEnvironment = (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!name.trim()) return; setCustom((current) => [...current, name.trim()]); setName(""); setCreating(false); };
  return <div className="settings-stack"><SettingsIntro title="Environments" description="Separate operational context from provider mode. CHIMERA uses these environments to keep evaluation and production boundaries explicit." action={<button className="button button-primary" type="button" onClick={() => setCreating((value) => !value)}>{creating ? "Cancel" : "Create environment"}</button>} />{creating && <form className="settings-create-row" onSubmit={addEnvironment}><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Environment name" aria-label="Environment name" /><button className="button button-secondary" type="submit">Add environment</button></form>}<div className="environment-table"><div className="environment-row environment-header"><span>Name</span><span>Execution context</span><span>Provider mode</span><span>Status</span></div><EnvironmentRow name="Production" context="Protected operational workspace" mode="Explicit enablement" status="Protected" /><EnvironmentRow name="Demo" context="Synthetic recovery journeys" mode="LOCAL" status="Active" /><EnvironmentRow name="Evaluation" context="Reproducible Arena batches" mode="LOCAL" status="Active" />{custom.map((item) => <EnvironmentRow name={item} context="Custom workspace" mode="LOCAL" status="Ready" key={item} />)}</div><SettingsCard title="Custom environments" description="Additional environments are local workspace labels in this demo. They do not create external infrastructure."><div className="settings-empty-row">No external environments connected.</div></SettingsCard></div>;
}

function ProviderModeSettings() {
  const [mode, setMode] = useState("LOCAL");
  const [saved, setSaved] = useState(false);
  return <div className="settings-stack"><SettingsIntro title="Provider Modes" description="Choose the default execution boundary for this workspace. Provider readiness remains managed under Providers." action={<Link className="button button-secondary" href="/providers">Open provider readiness</Link>} /><SettingsCard title="Default provider mode" description="The default mode used by demo and evaluation workflows." footer={<SaveButton saved={saved} onClick={() => setSaved(true)} />}><label className="settings-select-row"><span>Workspace default</span><select value={mode} onChange={(event) => { setMode(event.target.value); setSaved(false); }}><option value="LOCAL">LOCAL · Local demo provider</option><option value="MOCK">MOCK · Mock verification</option><option value="TEST">TEST · Explicit test provider</option></select></label><div className="settings-info-line"><InfoIcon size={14} /><span>LIVE is not selectable from workspace settings. It requires backend eligibility and an explicit execution control.</span></div></SettingsCard><div className="settings-mode-list"><ModeRow name="Local demo provider" mode="LOCAL" detail="Safe deterministic execution with synthetic receipts." status="Available" /><ModeRow name="Mock verification" mode="MOCK" detail="Provider-shaped verification without a live request." status="Available" /><ModeRow name="Razorpay TEST" mode="TEST" detail="Use only when Razorpay test credentials and a returned reference are present." status="Needs readiness" /><ModeRow name="Live execution" mode="LIVE" detail="Explicitly disabled in this workspace." status="Disabled" disabled /></div></div>;
}

function DecisionPolicySettings() {
  return <div className="settings-stack"><SettingsIntro title="Decision Policy" description="Read the control rules that keep recovery actions economically and operationally bounded." action={<Link className="button button-secondary" href="/system/decision-engine">Open decision engine</Link>} /><SettingsCard title="Decision authority" description="The financial action is selected by the stored deterministic engine." footer={<span className="settings-status settings-status-mint"><span />Authoritative</span>}><div className="policy-readout"><strong>Deterministic recovery engine</strong><span>Model estimates support the decision; policy validation selects the permissible action.</span></div></SettingsCard><SettingsCard title="Active constraints" description="Constraints are evaluated by the backend before an intervention can execute."><div className="settings-check-list"><CheckRow label="Expected-net scoring includes action cost" /><CheckRow label="Fatigue treatment is included in candidate comparison" /><CheckRow label="Blocked candidates remain visible with a reason" /><CheckRow label="Stored decision cannot be replaced by the UI" /></div></SettingsCard></div>;
}

function SafetySettings() {
  const [confirm, setConfirm] = useState(true);
  const [live, setLive] = useState(false);
  return <div className="settings-stack"><SettingsIntro title="Safety" description="Guardrails for actions that can affect customers, providers, or financial state." /><div className="settings-alert"><ShieldIcon size={16} /><div><strong>Live execution is disabled</strong><span>Local, mock, and test boundaries remain available for buildathon demonstration.</span></div></div><SettingsCard title="Action controls" description="Require an explicit operator decision before a stored action crosses its execution boundary."><ToggleRow label="Confirm recovery actions" detail="Keep execution behind an explicit operator click in Decision Room." checked={confirm} onChange={setConfirm} /><ToggleRow label="Allow live provider mode" detail="Requires backend enablement, provider readiness, and a separate confirmation." checked={live} onChange={setLive} /></SettingsCard><SettingsCard title="Safety posture" description="These controls are reflected in the System Health and Methodology surfaces."><div className="settings-check-list"><CheckRow label="Provider acceptance is not shown as recovery" /><CheckRow label="Webhook or outcome authority determines recovered state" /><CheckRow label="Raw credentials and provider responses stay hidden" /></div></SettingsCard></div>;
}

function AuditDataSettings() {
  const [retention, setRetention] = useState("90");
  const [saved, setSaved] = useState(false);
  return <div className="settings-stack"><SettingsIntro title="Audit & Data" description="Control how this workspace presents and retains synthetic evidence." /><SettingsCard title="Audit retention" description="Retention is a demo workspace setting until a persisted workspace configuration endpoint is connected." footer={<SaveButton saved={saved} onClick={() => setSaved(true)} />}><label className="settings-select-row"><span>Keep audit records for</span><select value={retention} onChange={(event) => { setRetention(event.target.value); setSaved(false); }}><option value="30">30 days</option><option value="90">90 days</option><option value="365">1 year</option><option value="forever">Until manually cleared</option></select></label></SettingsCard><SettingsCard title="Data boundary" description="What this workspace is allowed to display."><div className="settings-check-list"><CheckRow label="Synthetic records are clearly labeled" /><CheckRow label="Provider references are sanitized before display" /><CheckRow label="Audit events remain read-only in the UI" /></div></SettingsCard></div>;
}

function SettingsIntro({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="settings-intro"><div><h2>{title}</h2><p>{description}</p></div>{action}</div>;
}

function SettingsCard({ title, description, children, footer }: { title: string; description: string; children: React.ReactNode; footer?: React.ReactNode }) {
  return <section className="settings-card"><div className="settings-card-head"><h2>{title}</h2><p>{description}</p></div><div className="settings-card-body">{children}</div>{footer && <div className="settings-card-footer">{footer}</div>}</section>;
}

function SaveButton({ saved, onClick }: { saved: boolean; onClick: () => void }) {
  return <button className="button button-secondary" type="button" onClick={onClick}>{saved ? "Saved" : "Save"}</button>;
}

function ToggleRow({ label, detail, defaultChecked, checked, onChange }: { label: string; detail: string; defaultChecked?: boolean; checked?: boolean; onChange?: (value: boolean) => void }) {
  return <label className="settings-toggle-row"><span><strong>{label}</strong><small>{detail}</small></span><input type="checkbox" defaultChecked={defaultChecked} checked={checked} onChange={(event) => onChange?.(event.target.checked)} /></label>;
}

function EnvironmentRow({ name, context, mode, status }: { name: string; context: string; mode: string; status: string }) {
  return <div className="environment-row"><strong>{name}</strong><span>{context}</span><code>{mode}</code><span className="settings-status settings-status-mint"><span />{status}</span></div>;
}

function ModeRow({ name, mode, detail, status, disabled = false }: { name: string; mode: string; detail: string; status: string; disabled?: boolean }) {
  return <div className={`settings-mode-row ${disabled ? "disabled" : ""}`}><div><strong>{name}</strong><span>{detail}</span></div><code>{mode}</code><span className="settings-status"><span />{status}</span></div>;
}

function CheckRow({ label }: { label: string }) {
  return <div className="settings-check-row"><CheckIcon size={14} /><span>{label}</span></div>;
}
