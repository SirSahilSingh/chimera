"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertIcon, ArrowLeftIcon, AuditIcon, ChevronDownIcon, FlaskIcon, GridIcon, ListIcon, SearchIcon, SettingsIcon, ShieldIcon } from "./icons";

type NavItem = {
  href?: string;
  label: string;
  icon: React.ComponentType<{ size?: number }>;
  disabled?: boolean;
};

type NavSection = {
  label: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  { label: "Recovery Operations", items: [
    { href: "/cases", label: "Case Queue", icon: ListIcon },
    { href: "/cases?status=DECIDED", label: "Action Queue", icon: AlertIcon },
    { href: "/escalations", label: "Escalations", icon: AlertIcon },
    { href: "/retries/scheduled", label: "Scheduled Retries", icon: ShieldIcon },
  ] },
  { label: "Intelligence", items: [
    { href: "/intelligence/failures", label: "Failure Patterns", icon: SearchIcon },
    { href: "/intelligence/performance", label: "Recovery Outcomes", icon: GridIcon },
    { href: "/learn", label: "Outcome Learning", icon: SearchIcon },
  ] },
  { label: "System", items: [
    { href: "/system/health", label: "System Health", icon: ShieldIcon },
    { href: "/system/decision-engine", label: "Decision Engine", icon: ShieldIcon },
    { href: "/audit", label: "Audit Trail", icon: AuditIcon },
  ] },
  { label: "Providers", items: [
    { href: "/providers", label: "Provider Readiness", icon: ShieldIcon },
  ] },
  { label: "Evaluation Lab", items: [
    { href: "/checkout", label: "Initial Checkout", icon: ShieldIcon },
    { href: "/demo", label: "Demo Scenarios", icon: FlaskIcon },
    { href: "/arena", label: "Recovery Arena", icon: GridIcon },
    { href: "/methodology", label: "Methodology & Guardrails", icon: ShieldIcon },
  ] },
];

const settingsItems = [
  { href: "/settings/general", label: "General" },
  { href: "/settings/environments", label: "Environments" },
  { href: "/settings/provider-modes", label: "Provider Modes" },
  { href: "/settings/decision-policy", label: "Decision Policy" },
  { href: "/settings/safety", label: "Safety" },
  { href: "/settings/audit-data", label: "Audit & Data" },
];

function isItemActive(pathname: string, search: string, href?: string) {
  if (!href) return false;
  const [route, query] = href.split("?");
  if (query) return pathname === route && new URLSearchParams(search).toString() === query;
  if (route === "/") return pathname === "/" && !search;
  if (route === "/cases") return pathname === route && !search.includes("status=DECIDED");
  return pathname === route || pathname.startsWith(`${route}/`);
}

function sectionIsActive(section: NavSection, pathname: string, search: string) {
  return section.items.some((item) => isItemActive(pathname, search, item.href));
}

function pageName(pathname: string, search: string) {
  if (pathname === "/" && search.includes("view=engine")) return "Decision Engine";
  if (pathname === "/") return "Overview";
  if (pathname.startsWith("/cases/")) return "Decision Room";
  if (pathname === "/cases" && search.includes("status=DECIDED")) return "Action Queue";
  if (pathname === "/cases") return "Case Queue";
  if (pathname.startsWith("/escalations")) return "Escalations";
  if (pathname.startsWith("/retries/scheduled")) return "Scheduled Retries";
  if (pathname.startsWith("/arena")) return "Recovery Arena";
  if (pathname.startsWith("/methodology")) return "Methodology & Guardrails";
  if (pathname.startsWith("/demo")) return "Demo Scenarios";
  if (pathname.startsWith("/checkout")) return "Initial Checkout";
  if (pathname.startsWith("/intelligence/failures")) return "Failure Patterns";
  if (pathname.startsWith("/intelligence/performance")) return "Recovery Outcomes";
  if (pathname.startsWith("/learn")) return "Outcome Learning";
  if (pathname.startsWith("/audit")) return "Audit Trail";
  if (pathname.startsWith("/system/health")) return "System Health";
  if (pathname.startsWith("/system/decision-engine")) return "Decision Engine";
  if (pathname.startsWith("/providers")) return "Provider Readiness";
  if (pathname.startsWith("/settings/environments")) return "Environments";
  if (pathname.startsWith("/settings/provider-modes")) return "Provider Modes";
  if (pathname.startsWith("/settings/decision-policy")) return "Decision Policy";
  if (pathname.startsWith("/settings/safety")) return "Safety";
  if (pathname.startsWith("/settings/audit-data")) return "Audit & Data";
  if (pathname.startsWith("/settings")) return "General";
  return "Overview";
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const settingsMode = pathname.startsWith("/settings");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => Object.fromEntries(navSections.map((section) => [section.label, true])));

  useEffect(() => {
    const nextSearch = window.location.search.slice(1);
    setSearch(nextSearch);
    const activeSection = navSections.find((section) => sectionIsActive(section, pathname, nextSearch));
    if (activeSection) setExpanded((current) => ({ ...current, [activeSection.label]: true }));
  }, [pathname]);

  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="CHIMERA overview">
        <span className="brand-mark"><span /></span>
        <span className="brand-name">CHIMERA</span>
        <span className="workspace-plan">Demo</span>
        <ChevronDownIcon size={13} />
      </Link>

      <button className="sidebar-search" type="button" aria-label="Find"><SearchIcon size={17} /><span>Find</span><kbd>F</kbd></button>

      {settingsMode ? <SettingsNavigation pathname={pathname} /> : <nav className="side-nav" aria-label="Primary navigation">
        <Link href="/" className={`nav-item nav-overview ${pathname === "/" && !search.includes("view=engine") ? "active" : ""}`}><GridIcon size={16} /><span>Overview</span></Link>
        <div className="nav-rule" />
        {navSections.map((section, index) => {
          const active = sectionIsActive(section, pathname, search);
          const open = expanded[section.label];
          return <div className={`nav-section ${active ? "section-active" : ""}`} key={section.label}>
            <button className="nav-section-toggle" type="button" aria-expanded={open} onClick={() => setExpanded((current) => ({ ...current, [section.label]: !open }))}>
              <span>{section.label}</span><ChevronDownIcon size={13} className={open ? "" : "collapsed"} />
            </button>
            {open && <div className="nav-children">{section.items.map((item) => {
              const itemActive = isItemActive(pathname, search, item.href);
              if (item.disabled) return <span className="nav-item nav-child disabled" aria-disabled="true" title="Coming next" key={item.label}><item.icon size={15} /><span>{item.label}</span></span>;
              return <Link href={item.href!} className={`nav-item nav-child ${itemActive ? "active" : ""}`} key={item.label}><item.icon size={15} /><span>{item.label}</span>{itemActive && <span className="nav-pip" />}</Link>;
            })}</div>}
            {index === 1 && <div className="nav-rule section-rule" />}
          </div>;
        })}
      </nav>}

      <div className="sidebar-footer">
        {!settingsMode && <Link href="/settings/general" className="sidebar-settings-link"><SettingsIcon size={15} /><span>Settings</span></Link>}
        <div className="sidebar-status"><span className="status-dot online" /><span>Agent operational</span></div>
        <div className="workspace-line"><span className="avatar">RO</span><div><strong>Recovery Ops</strong><small>Synthetic workspace</small></div><ChevronDownIcon size={13} /></div>
      </div>
    </aside>
    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-project"><span className="project-mark" /><strong>chimera</strong><ChevronDownIcon size={13} /></div>
        <div className="topbar-title">{settingsMode ? <><span>Project Settings</span><i>/</i>{pageName(pathname, search)}</> : pageName(pathname, search)}</div>
        <div className="topbar-agent"><GridIcon size={15} /><span>Agent</span></div>
      </header>
      <div className="page-wrap">{children}</div>
    </main>
  </div>;
}

function SettingsNavigation({ pathname }: { pathname: string }) {
  return <nav className="side-nav settings-side-nav" aria-label="Settings navigation">
    <Link href="/" className="settings-back"><ArrowLeftIcon size={15} /><span>Settings</span></Link>
    <div className="settings-nav-list">{settingsItems.map((item) => <Link href={item.href} className={`nav-item settings-nav-item ${pathname === item.href ? "active" : ""}`} key={item.href}><SettingsIcon size={14} /><span>{item.label}</span></Link>)}</div>
  </nav>;
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode; eyebrow?: string }) {
  return <div className="page-header"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-header-action">{action}</div>}</div>;
}

export function Button({ children, kind = "primary", onClick, disabled, type = "button", className = "" }: { children: React.ReactNode; kind?: "primary" | "secondary" | "quiet" | "danger"; onClick?: () => void; disabled?: boolean; type?: "button" | "submit"; className?: string }) {
  return <button type={type} className={`button button-${kind} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

export function StatusBadge({ status }: { status: string }) {
  const tone = status === "RECOVERED" || status === "ACTION_EXECUTED" || status.endsWith("_VERIFIED") || status === "OPERATIONAL" || status === "AUTHORITATIVE" ? "success" : status === "NEW" || status === "NOT_CONFIGURED" ? "neutral" : status === "DECIDED" || status === "CONFIGURED" || status === "TEST_READY" ? "info" : status === "CLOSED" || status === "UNRECOVERED" || status === "READ_ONLY" ? "muted" : "warning";
  return <span className={`status-badge ${tone}`}><span className="status-dot" />{status.replaceAll("_", " ")}</span>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state-panel error-state"><AlertIcon size={20} /><div><strong>Something needs attention</strong><p>{message}</p>{onRetry && <Button kind="secondary" onClick={onRetry}>Try again</Button>}</div></div>;
}

export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return <div className="loading-state"><span className="loader" /><span>{label}</span></div>;
}
