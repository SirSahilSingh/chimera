"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertIcon, ArrowLeftIcon, AuditIcon, CheckIcon, ChevronDownIcon, FlaskIcon, GridIcon, ListIcon, SearchIcon, ShieldIcon, TuneIcon } from "./icons";
import logo from "../chimera-logo.png";

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
    { href: "/demo", label: "Demo Scenarios", icon: FlaskIcon },
    { href: "/arena", label: "Policy Lab", icon: GridIcon },
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

const searchItems = [
  { href: "/", label: "Overview", detail: "Command Center", icon: GridIcon },
  ...navSections.flatMap((section) => section.items.map((item) => ({ href: item.href!, label: item.label, detail: section.label, icon: item.icon }))),
  ...settingsItems.map((item) => ({ href: item.href, label: item.label, detail: "Settings", icon: TuneIcon })),
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
  if (pathname.startsWith("/arena")) return "Policy Lab";
  if (pathname.startsWith("/methodology")) return "Methodology & Guardrails";
  if (pathname.startsWith("/demo")) return "Demo Scenarios";
  if (pathname.startsWith("/checkout")) return "Demo Scenarios";
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
  const router = useRouter();
  const settingsMode = pathname.startsWith("/settings");
  const [search, setSearch] = useState("");
  const [findQuery, setFindQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => Object.fromEntries(navSections.map((section) => [section.label, false])));
  const [hoveredSection, setHoveredSection] = useState<string | null>(null);
  const [selectedSearchIndex, setSelectedSearchIndex] = useState(0);

  useEffect(() => {
    const nextSearch = window.location.search.slice(1);
    setSearch(nextSearch);
    const activeSection = navSections.find((section) => sectionIsActive(section, pathname, nextSearch));
    if (activeSection) setExpanded((current) => ({ ...current, [activeSection.label]: true }));
  }, [pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key.toLowerCase() === "f" && target?.tagName !== "INPUT" && target?.tagName !== "TEXTAREA") {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const closeSearch = () => {
    setSearchOpen(false);
    setFindQuery("");
    setSelectedSearchIndex(0);
  };

  const openSearch = () => {
    setSearchOpen(true);
    setFindQuery("");
    setSelectedSearchIndex(0);
  };

  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="CHIMERA overview">
        <Image className="brand-logo" src={logo} alt="" width={23} height={23} priority />
        <span className="brand-name">CHIMERA</span>
        <span className="workspace-plan">Demo</span>
        <ChevronDownIcon size={13} />
      </Link>

      <button className="sidebar-search" type="button" aria-label="Find" onClick={openSearch}><SearchIcon size={17} /><span>Find</span><kbd>F</kbd></button>

      {settingsMode ? <SettingsNavigation pathname={pathname} /> : <nav className="side-nav" aria-label="Primary navigation">
        <Link href="/" className={`nav-item nav-overview ${pathname === "/" && !search.includes("view=engine") ? "active" : ""}`}><GridIcon size={16} /><span>Overview</span></Link>
        <div className="nav-rule" />
        {navSections.map((section, index) => {
          const active = sectionIsActive(section, pathname, search);
          const open = expanded[section.label] || hoveredSection === section.label;
          return <div className={`nav-section ${active ? "section-active" : ""} ${open ? "open" : ""}`} key={section.label} onMouseEnter={() => setHoveredSection(section.label)} onMouseLeave={() => setHoveredSection((current) => current === section.label ? null : current)}>
            <button className="nav-section-toggle" type="button" aria-expanded={open} onClick={() => setExpanded((current) => ({ ...current, [section.label]: !current[section.label] }))}>
              <span>{section.label}</span><span className="nav-section-arrow"><ChevronDownIcon size={13} className={open ? "" : "collapsed"} /></span>
            </button>
            <div className="nav-children" aria-hidden={!open}><div className="nav-children-inner">{section.items.map((item) => {
              const itemActive = isItemActive(pathname, search, item.href);
              if (item.disabled) return <span className="nav-item nav-child disabled" aria-disabled="true" title="Coming next" key={item.label}><item.icon size={15} /><span>{item.label}</span></span>;
              return <Link href={item.href!} className={`nav-item nav-child ${itemActive ? "active" : ""}`} key={item.label}><item.icon size={15} /><span>{item.label}</span></Link>;
            })}</div></div>
            {index === 1 && <div className="nav-rule section-rule" />}
          </div>;
        })}
        <div className="nav-rule settings-rule" />
        <Link href="/settings/general" className={`nav-item nav-settings ${settingsMode ? "active" : ""}`}><TuneIcon size={16} /><span>Settings</span></Link>
      </nav>}

    </aside>
    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-project"><span className="project-mark" /></div>
        <div className="topbar-title">{settingsMode ? <><span>Project Settings</span><i>/</i>{pageName(pathname, search)}</> : pageName(pathname, search)}</div>
      </header>
      <div className="page-wrap">{children}</div>
    </main>
    {searchOpen && <SearchPalette query={findQuery} onQueryChange={(value) => { setFindQuery(value); setSelectedSearchIndex(0); }} onClose={closeSearch} selectedIndex={selectedSearchIndex} onSelectedIndexChange={setSelectedSearchIndex} onNavigate={(href) => { closeSearch(); router.push(href); }} />}
  </div>;
}

function SearchPalette({ query, onQueryChange, onClose, selectedIndex, onSelectedIndexChange, onNavigate }: { query: string; onQueryChange: (value: string) => void; onClose: () => void; selectedIndex: number; onSelectedIndexChange: (value: number) => void; onNavigate: (href: string) => void }) {
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return searchItems.filter((item) => !needle || `${item.label} ${item.detail}`.toLowerCase().includes(needle));
  }, [query]);

  useEffect(() => {
    if (!results.length) return;
    const nextIndex = Math.min(selectedIndex, results.length - 1);
    if (nextIndex !== selectedIndex) onSelectedIndexChange(nextIndex);
  }, [onSelectedIndexChange, results.length, selectedIndex]);

  return <div className="search-layer" role="presentation" onMouseDown={onClose}>
    <div className="search-palette" role="dialog" aria-label="Find in CHIMERA" onMouseDown={(event) => event.stopPropagation()}>
      <div className="search-palette-input"><SearchIcon size={19} /><input autoFocus value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={(event) => {
        if (event.key === "ArrowDown") { event.preventDefault(); onSelectedIndexChange(results.length ? (selectedIndex + 1) % results.length : 0); }
        if (event.key === "ArrowUp") { event.preventDefault(); onSelectedIndexChange(results.length ? (selectedIndex - 1 + results.length) % results.length : 0); }
        if (event.key === "Enter" && results[selectedIndex]) { event.preventDefault(); onNavigate(results[selectedIndex].href); }
      }} placeholder="Find" aria-label="Find" /><button type="button" onClick={onClose} aria-label="Close search">Esc</button></div>
      <div className="search-results" role="listbox" aria-label="Suggestions">
        {results.length ? results.slice(0, 8).map((item, index) => <Link href={item.href} role="option" aria-selected={index === selectedIndex} className={`search-result ${index === selectedIndex ? "selected" : ""}`} key={item.href} onMouseEnter={() => onSelectedIndexChange(index)} onClick={onClose}><span className="search-result-icon"><item.icon size={17} /></span><span><strong>{item.label}</strong><small>{item.detail}</small></span></Link>) : <div className="search-empty">No matching workspace pages</div>}
      </div>
    </div>
  </div>;
}

function SettingsNavigation({ pathname }: { pathname: string }) {
  return <nav className="side-nav settings-side-nav" aria-label="Settings navigation">
    <Link href="/" className="settings-back"><ArrowLeftIcon size={15} /><span>Settings</span></Link>
    <div className="settings-nav-list">{settingsItems.map((item) => <Link href={item.href} className={`nav-item settings-nav-item ${pathname === item.href ? "active" : ""}`} key={item.href}><TuneIcon size={14} /><span>{item.label}</span></Link>)}</div>
  </nav>;
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode; eyebrow?: string }) {
  return <div className="page-header"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-header-action">{action}</div>}</div>;
}

export function Button({ children, kind = "primary", onClick, disabled, type = "button", className = "" }: { children: React.ReactNode; kind?: "primary" | "secondary" | "quiet" | "danger"; onClick?: () => void; disabled?: boolean; type?: "button" | "submit"; className?: string }) {
  return <button type={type} className={`button button-${kind} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

export type DropdownOption = { value: string; label: string; tone?: "neutral" | "blue" | "mint" | "amber" | "red" | "violet" };

export function DropdownField({ label, value, onChange, options, className = "", disabled = false }: { label: string; value: string; onChange: (value: string) => void; options: DropdownOption[]; className?: string; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const closeOnOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeOnOutside); document.removeEventListener("keydown", closeOnEscape); };
  }, [open]);

  return <div className={`dropdown-field ${open ? "open" : ""} ${className}`} ref={rootRef}>
    <button className="dropdown-trigger" type="button" aria-haspopup="listbox" aria-expanded={open} disabled={disabled} onClick={() => setOpen((current) => !current)}>
      <span className="dropdown-trigger-label">{label}</span><span className="dropdown-trigger-value">{selected?.label ?? "Select"}</span><ChevronDownIcon size={13} />
    </button>
    {open && <div className="dropdown-menu" role="listbox" aria-label={label}>
      {options.map((option) => <button className={`dropdown-option ${option.value === value ? "selected" : ""}`} type="button" role="option" aria-selected={option.value === value} key={option.value} onClick={() => { onChange(option.value); setOpen(false); }}>
        <span className={`dropdown-dot ${option.tone ?? "neutral"}`} /><span className="dropdown-option-label">{option.label}</span>{option.value === value && <CheckIcon size={13} />}
      </button>)}
    </div>}
  </div>;
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
