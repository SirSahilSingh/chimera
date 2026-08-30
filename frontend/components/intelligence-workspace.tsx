import type { ReactNode } from "react";
import { ArrowRightIcon } from "./icons";

export function IntelligenceTitle({ title, action }: { title: string; action?: ReactNode }) {
  return <div className="workspace-titlebar intelligence-titlebar"><div><h1>{title}</h1></div>{action && <div className="workspace-actions">{action}</div>}</div>;
}

export function EvidenceBoundary({ sampleSize, providerModes = [], lastUpdated = "On refresh" }: { sampleSize: number; providerModes?: string[]; lastUpdated?: string }) {
  return <div className="evidence-boundary"><span>Data: synthetic stored records</span><span>Sample size: {sampleSize} cases</span><span>Provider modes: {providerModes.length ? providerModes.join(", ") : "stored case records"}</span><span>Last updated: {lastUpdated}</span><strong>Interpretation: observed, not causal</strong></div>;
}

export function IntelligenceMetric({ label, value, note, tone = "default" }: { label: string; value: string; note: string; tone?: "default" | "mint" | "amber" | "red" }) {
  return <div className={`intelligence-metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

export function IntelligencePanel({ title, note, children, className = "" }: { title: string; note?: string; children: ReactNode; className?: string }) {
  return <section className={`intelligence-panel ${className}`}><div className="intelligence-panel-head"><h2>{title}</h2>{note && <span>{note}</span>}</div>{children}</section>;
}

export function DeepLink({ href, children }: { href: string; children: ReactNode }) {
  return <a className="intel-deep-link" href={href}>{children}<ArrowRightIcon size={14} /></a>;
}

export function IntelEmpty({ label }: { label: string }) {
  return <div className="intel-empty">{label}</div>;
}
