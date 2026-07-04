import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../lib/api-client";
import { MuscleLogo } from "../components/mascot";

export function AppShell() {
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2" aria-label="Testo home">
              <MuscleLogo size={26} />
              <span className="text-sm font-bold uppercase tracking-[0.2em] text-ink-100">Testo</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <NavItem to="/" end>
                Dashboard
              </NavItem>
              <NavItem to="/cycles">Cycles</NavItem>
              <NavItem to="/runs">Runs</NavItem>
              <NavItem to="/compare">Compare</NavItem>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <HealthDot />
            <AdvancedMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({ to, end, children }: { to: string; end?: boolean; children: string }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          "rounded-md px-3 py-1.5 transition-colors",
          isActive ? "bg-ink-800 text-ink-100" : "text-ink-300 hover:bg-ink-850 hover:text-ink-100"
        ].join(" ")
      }
    >
      {children}
    </NavLink>
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

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
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
          <MenuLink to="/advanced/execution" onClick={() => setOpen(false)}>
            Legacy Execution
          </MenuLink>
          <MenuLink to="/settings/ai" onClick={() => setOpen(false)}>
            AI Settings
          </MenuLink>
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
