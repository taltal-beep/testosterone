import { useCallback, useEffect, useRef, useState, type ComponentType, type RefObject } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../lib/api-client";
import { MuscleLogo } from "../components/mascot";
import { BackgroundArt } from "../components/BackgroundArt";
import { DemoBadge } from "../components/StaticBuildBanner";
import { Icons } from "../components/ui";

type NavLinkSpec = { to: string; label: string; icon: ComponentType; end?: boolean };

const PRIMARY_LINKS: NavLinkSpec[] = [
  { to: "/", label: "Dashboard", icon: Icons.HomeIcon, end: true },
  { to: "/cycles", label: "Cycles", icon: Icons.CyclesIcon },
  { to: "/runs", label: "Runs", icon: Icons.RunsIcon },
  { to: "/compare", label: "Compare", icon: Icons.CompareIcon }
];

const ADVANCED_LINKS: NavLinkSpec[] = [
  { to: "/quick-run", label: "Quick run", icon: Icons.BoltIcon },
  { to: "/resources", label: "Resources", icon: Icons.KeyIcon },
  { to: "/try", label: "Try a file", icon: Icons.UploadIcon },
  { to: "/settings/ai", label: "AI settings", icon: Icons.SparkIcon }
];

const DOCS_URL = "https://taltal-beep.github.io/testosterone/docs/";

/** Breadcrumb label for the current page, from the first path segment. */
function sectionLabel(pathname: string): string {
  const link = [...PRIMARY_LINKS, ...ADVANCED_LINKS].find((l) =>
    l.to === "/" ? pathname === "/" : pathname === l.to || pathname.startsWith(`${l.to}/`)
  );
  return link?.label ?? "Not found";
}

/**
 * Desktop: a floating glass sidebar (nav, Tools section, docs link) beside
 * the page. Below `lg` the sidebar is hidden and a top bar with a disclosure
 * menu takes its place.
 */
export function AppShell() {
  const { pathname } = useLocation();
  return (
    <div className="min-h-full">
      {/* Inside a landmark, like all content, so screen-reader region navigation finds it. */}
      <nav aria-label="Skip links">
        <a
          href="#main"
          className="sr-only z-50 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
        >
          Skip to content
        </a>
      </nav>
      <BackgroundArt />
      <aside className="glass-panel fixed inset-y-4 left-4 z-20 hidden w-64 flex-col overflow-y-auto px-4 py-6 lg:flex">
        <Link to="/" className="flex items-center justify-center gap-2.5 pb-6" aria-label="Testo home">
          <MuscleLogo size={26} />
          <span className="text-sm font-bold uppercase tracking-[0.3em] text-white">Testo</span>
        </Link>
        <div className="mb-5 h-px bg-gradient-to-r from-transparent via-white/25 to-transparent" aria-hidden />
        <nav aria-label="Sections" className="flex flex-col gap-1 text-sm">
          {PRIMARY_LINKS.map((link) => (
            <NavItem key={link.to} link={link} />
          ))}
          <p className="mb-1 mt-5 px-4 text-[11px] font-bold uppercase tracking-wider text-white">Tools</p>
          {ADVANCED_LINKS.map((link) => (
            <NavItem key={link.to} link={link} />
          ))}
        </nav>
        <DocsLink />
      </aside>

      <header className="sticky top-0 z-30 border-b border-white/5 bg-ink-950/80 backdrop-blur-xl lg:hidden">
        <div className="relative flex items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2" aria-label="Testo home">
            <MuscleLogo size={26} />
            <span className="text-sm font-bold uppercase tracking-[0.2em] text-white">Testo</span>
          </Link>
          <div className="flex items-center gap-3">
            <DemoBadge />
            <UserBadge />
            <HealthDot />
            <MobileMenu />
          </div>
        </div>
      </header>

      <div className="lg:pl-[18rem]">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:pt-5">
          <header className="mb-5 hidden items-center justify-between gap-4 lg:flex">
            <p className="text-xs text-ink-300">
              Testo <span className="text-ink-500">/</span> <span className="font-semibold text-white">{sectionLabel(pathname)}</span>
            </p>
            <div className="flex items-center gap-4">
              <DemoBadge />
              <UserBadge />
              <HealthDot />
            </div>
          </header>
          <main id="main" tabIndex={-1} className="outline-none">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

function NavItem({ link, size = "compact" }: { link: NavLinkSpec; size?: "compact" | "touch" }) {
  const Icon = link.icon;
  return (
    <NavLink
      to={link.to}
      end={link.end}
      className={({ isActive }) =>
        [
          "group flex items-center gap-3 rounded-2xl px-4 font-medium transition-colors",
          size === "touch" ? "py-2.5" : "py-2",
          isActive ? "bg-ink-800/80 text-white shadow-lg shadow-black/20" : "text-ink-300 hover:bg-ink-800/40 hover:text-white"
        ].join(" ")
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={[
              "flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-xl transition-colors",
              isActive ? "bg-brand-500 text-white" : "bg-ink-800 text-brand-400 group-hover:bg-ink-700"
            ].join(" ")}
          >
            <Icon />
          </span>
          {link.label}
        </>
      )}
    </NavLink>
  );
}

function DocsLink() {
  return (
    <a
      href={DOCS_URL}
      target="_blank"
      rel="noreferrer"
      className="mt-auto flex items-center gap-3 rounded-2xl px-4 py-2 text-sm font-medium text-ink-300 transition-colors hover:bg-ink-800/40 hover:text-white"
    >
      <span className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-xl bg-ink-800 text-brand-400">
        <Icons.HelpIcon />
      </span>
      Docs
    </a>
  );
}

/** Closes a popup on a mousedown outside `ref` or on Escape, which also returns focus to `trigger`. */
function useDismiss(
  open: boolean,
  close: () => void,
  ref: RefObject<HTMLElement | null>,
  trigger: RefObject<HTMLElement | null>
) {
  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      close();
      trigger.current?.focus();
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, close, ref, trigger]);
}

/**
 * Below the `lg` breakpoint the sidebar nav and its Tools section don't fit
 * next to the logo, so both collapse into one disclosure panel under the header.
 */
function MobileMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const { pathname } = useLocation();

  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, ref, buttonRef);

  // Close on navigation, including back/forward.
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div
      ref={ref}
      className="lg:hidden"
      // Tabbing past the last link closes the panel instead of leaving it over the page.
      onBlur={(e) => {
        if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) close();
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex h-11 w-11 items-center justify-center rounded-xl text-ink-300 transition-colors hover:bg-ink-800 hover:text-white"
        aria-label="Menu"
        aria-expanded={open}
        aria-controls="mobile-nav"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path d={open ? "M5 5l10 10M15 5L5 15" : "M3 6h14M3 10h14M3 14h14"} />
        </svg>
      </button>
      <nav
        id="mobile-nav"
        aria-label="Main"
        hidden={!open}
        // Covers a tap on the link for the page that is already open.
        onClick={(e) => {
          if ((e.target as Element).closest("a")) close();
        }}
        className="absolute inset-x-0 top-full border-b border-white/5 bg-ink-950/95 px-4 py-3 text-sm shadow-xl backdrop-blur-xl"
      >
        <div className="flex flex-col gap-1">
          {PRIMARY_LINKS.map((link) => (
            <NavItem key={link.to} link={link} size="touch" />
          ))}
        </div>
        <p className="mt-3 px-4 text-[11px] font-bold uppercase tracking-wider text-white">Tools</p>
        <div className="mt-1 flex flex-col gap-1">
          {ADVANCED_LINKS.map((link) => (
            <NavItem key={link.to} link={link} size="touch" />
          ))}
        </div>
      </nav>
    </div>
  );
}

/** Who is signed in, when the server runs with per-user accounts (TESTO_AUTH=accounts). */
function UserBadge() {
  const query = useQuery({
    queryKey: ["who-am-i"],
    queryFn: () => apiClient.getWhoAmI(),
    staleTime: 5 * 60_000,
    retry: false
  });
  const me = query.data;
  if (!me || me.auth_mode !== "accounts" || !me.signed_in) return null;
  return (
    <form method="post" action="/api/v1/auth/logout" className="flex items-center gap-2 text-xs text-ink-300" data-testid="user-badge">
      <span>
        <span className="font-semibold text-white">{me.username}</span> · {me.role}
      </span>
      <button type="submit" className="rounded-lg px-2 py-1 text-ink-300 hover:bg-ink-800/60 hover:text-white">
        Sign out
      </button>
    </form>
  );
}

function HealthDot() {
  const query = useQuery({
    queryKey: ["health-ready"],
    queryFn: () => apiClient.getHealthReady(),
    refetchInterval: 30_000,
    retry: false
  });

  const health = query.data;
  const ok = health?.status === "ready";
  const color = query.isError ? "bg-danger-400" : ok ? "bg-success-400" : health ? "bg-warn-400" : "bg-ink-500";
  const label = query.isError ? "API unreachable" : ok ? "API connected" : health ? "API degraded" : "Checking…";

  const detail = health?.checks
    ? Object.entries(health.checks)
        .map(([name, check]) => `${name}: ${check.status}${check.detail ? ` — ${check.detail}` : ""}`)
        .join("\n")
    : label;

  return (
    <span
      className="group relative flex items-center gap-1.5 text-xs text-ink-300"
      data-testid="health-indicator"
      title={detail}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} aria-hidden />
      <span className="hidden sm:inline">{label}</span>
    </span>
  );
}
