import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../lib/api-client";
import { MuscleLogo } from "../components/mascot";

const PRIMARY_LINKS: { to: string; label: string; end?: boolean }[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/cycles", label: "Cycles" },
  { to: "/runs", label: "Runs" },
  { to: "/compare", label: "Compare" }
];

const ADVANCED_LINKS = [
  { to: "/quick-run", label: "Quick Run" },
  { to: "/settings/ai", label: "AI Settings" }
];

export function AppShell() {
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2" aria-label="Testo home">
              <MuscleLogo size={26} />
              <span className="text-sm font-bold uppercase tracking-[0.2em] text-ink-100">Testo</span>
            </Link>
            <nav className="hidden items-center gap-1 text-sm sm:flex">
              {PRIMARY_LINKS.map((link) => (
                <NavItem key={link.to} to={link.to} end={link.end}>
                  {link.label}
                </NavItem>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <HealthDot />
            <div className="hidden sm:block">
              <AdvancedMenu />
            </div>
            <MobileMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({
  to,
  end,
  size = "compact",
  children
}: {
  to: string;
  end?: boolean;
  size?: "compact" | "touch";
  children: string;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          "rounded-md px-3 transition-colors",
          size === "touch" ? "py-2.5" : "py-1.5",
          isActive ? "bg-ink-800 text-ink-100" : "text-ink-300 hover:bg-ink-850 hover:text-ink-100"
        ].join(" ")
      }
    >
      {children}
    </NavLink>
  );
}

/** Closes a popup on a mousedown outside `ref` or on Escape, which also returns focus to `trigger`. */
function useDismiss(
  open: boolean,
  close: () => void,
  ref: RefObject<HTMLElement>,
  trigger: RefObject<HTMLElement>
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
 * Below the `sm` breakpoint the inline nav and the Advanced dropdown don't fit
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
      className="sm:hidden"
      // Tabbing past the last link closes the panel instead of leaving it over the page.
      onBlur={(e) => {
        if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) close();
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded-md p-2 text-ink-300 transition-colors hover:bg-ink-850 hover:text-ink-100"
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
        className="absolute inset-x-0 top-full border-b border-ink-800 bg-ink-950 px-4 py-3 text-sm shadow-xl"
      >
        <div className="flex flex-col gap-1">
          {PRIMARY_LINKS.map((link) => (
            <NavItem key={link.to} to={link.to} end={link.end} size="touch">
              {link.label}
            </NavItem>
          ))}
        </div>
        <p className="mt-3 px-3 text-xs uppercase tracking-wider text-ink-500">Advanced</p>
        <div className="mt-1 flex flex-col gap-1">
          {ADVANCED_LINKS.map((link) => (
            <NavItem key={link.to} to={link.to} size="touch">
              {link.label}
            </NavItem>
          ))}
        </div>
      </nav>
    </div>
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
  const label = query.isError ? "API unreachable" : ok ? "All systems go" : health ? "Degraded" : "Checking…";

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

function AdvancedMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, ref, buttonRef);

  return (
    <div className="relative" ref={ref}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded-md px-3 py-1.5 text-sm text-ink-300 transition-colors hover:bg-ink-850 hover:text-ink-100"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        Advanced ▾
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 mt-1 w-48 overflow-hidden rounded-md border border-ink-700 bg-ink-900 py-1 shadow-xl"
        >
          {ADVANCED_LINKS.map((link) => (
            <MenuLink key={link.to} to={link.to} onClick={close}>
              {link.label}
            </MenuLink>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MenuLink({ to, onClick, children }: { to: string; onClick: () => void; children: string }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      role="menuitem"
      className={({ isActive }) =>
        [
          "block px-3 py-2 text-sm",
          isActive ? "bg-ink-800 text-ink-100" : "text-ink-300 hover:bg-ink-850 hover:text-ink-100"
        ].join(" ")
      }
    >
      {children}
    </NavLink>
  );
}
