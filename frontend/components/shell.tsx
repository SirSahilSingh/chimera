"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertIcon, AuditIcon, GridIcon, ListIcon, ShieldIcon, SearchIcon } from "./icons";

const navGroups = [
  { label: "Operations", items: [{ href: "/", label: "Command Center", icon: GridIcon }, { href: "/cases", label: "Recovery Cases", icon: ListIcon }, { href: "/cases?status=DECIDED", label: "Intervention Queue", icon: AlertIcon }] },
  { label: "Intelligence", items: [{ href: "/intelligence/failures", label: "Failure Intelligence", icon: SearchIcon }, { href: "/intelligence/performance", label: "Recovery Performance", icon: ShieldIcon }] },
  { label: "System", items: [{ href: "/audit", label: "Audit Trail", icon: AuditIcon }, { href: "/?view=engine", label: "Decision Engine", icon: ShieldIcon }] },
];

function isItemActive(pathname: string, search: string, href: string) {
  const route = href.split("?")[0];
  const query = href.split("?")[1];
  if (query) return pathname === route && new URLSearchParams(search).toString() === query;
  if (route === "/") return pathname === "/" && !search;
  if (route === "/cases") return pathname === route && !search.includes("status=DECIDED");
  return pathname === route || pathname.startsWith(`${route}/`);
}

function pageName(pathname: string) {
  if (pathname === "/") return "Command Center";
  if (pathname.startsWith("/cases/")) return "Decision Room";
  if (pathname === "/cases") return "Recovery Cases";
  if (pathname.startsWith("/intelligence/failures")) return "Failure Intelligence";
  if (pathname.startsWith("/intelligence/performance")) return "Recovery Performance";
  if (pathname.startsWith("/audit")) return "Audit Trail";
  return "Command Center";
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [search, setSearch] = useState("");
  useEffect(() => { setSearch(window.location.search.slice(1)); }, [pathname]);
  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="CHIMERA command center"><span className="brand-mark"><span /></span><span><strong>CHIMERA</strong><small>Revenue recovery intelligence</small></span></Link>
      <div className="sidebar-rule" />
      <nav className="side-nav" aria-label="Primary navigation">{navGroups.map((group) => <div className="nav-group" key={group.label}><span className="sidebar-label">{group.label}</span>{group.items.map(({ href, label, icon: Icon }) => { const active = isItemActive(pathname, search, href); return <Link key={`${href}-${label}`} href={href} className={`nav-item ${active ? "active" : ""}`}><Icon size={16} /><span>{label}</span>{active && <span className="nav-pip" />}</Link>; })}</div>)}</nav>
      <div className="sidebar-footer"><div className="system-status"><span className="status-dot online" /><span>Decision engine online</span></div><div className="workspace-line"><span className="avatar">RO</span><div><strong>Recovery Ops</strong><small>Synthetic workspace</small></div><span className="live-indicator" /></div></div>
    </aside>
    <main className="main-shell">
      <header className="topbar"><div className="breadcrumb"><span>CHIMERA</span><i>/</i><strong>{pageName(pathname)}</strong></div><div className="topbar-right"><span className="synthetic-badge"><span className="status-dot" /> Synthetic environment</span><span className="system-label">Policy engine v1.0.0</span></div></header>
      <div className="page-wrap">{children}</div>
    </main>
  </div>;
}

export function PageHeader({ title, description, action, eyebrow }: { title: string; description?: string; action?: React.ReactNode; eyebrow?: string }) {
  return <div className="page-header"><div>{eyebrow && <span className="page-eyebrow">{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-header-action">{action}</div>}</div>;
}

export function Button({ children, kind = "primary", onClick, disabled, type = "button", className = "" }: { children: React.ReactNode; kind?: "primary" | "secondary" | "quiet" | "danger"; onClick?: () => void; disabled?: boolean; type?: "button" | "submit"; className?: string }) {
  return <button type={type} className={`button button-${kind} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

export function StatusBadge({ status }: { status: string }) {
  const tone = status === "RECOVERED" || status === "ACTION_EXECUTED" ? "success" : status === "NEW" ? "neutral" : status === "DECIDED" ? "info" : status === "CLOSED" || status === "UNRECOVERED" ? "muted" : "warning";
  return <span className={`status-badge ${tone}`}><span className="status-dot" />{status.replaceAll("_", " ")}</span>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state-panel error-state"><AlertIcon size={20} /><div><strong>Something needs attention</strong><p>{message}</p>{onRetry && <Button kind="secondary" onClick={onRetry}>Try again</Button>}</div></div>;
}

export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return <div className="loading-state"><span className="loader" /><span>{label}</span></div>;
}
