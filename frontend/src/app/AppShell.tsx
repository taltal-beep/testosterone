import { NavLink, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6 font-sans">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Unified Quality Orchestration Dashboard</h1>
        <nav className="flex flex-wrap gap-3 text-sm text-slate-300">
          <NavItem to="/">Dashboard</NavItem>
          <NavItem to="/runner">Runner</NavItem>
          <NavItem to="/history">History</NavItem>
          <NavItem to="/compare">Compare</NavItem>
          <NavItem to="/execution">Legacy Execution</NavItem>
          <NavItem to="/settings/ai">AI Settings</NavItem>
        </nav>
      </header>
      <Outlet />
    </main>
  );
}

function NavItem({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "rounded px-3 py-1.5",
          isActive ? "bg-slate-800 text-white" : "bg-slate-900/40 text-slate-300 hover:bg-slate-800/70"
        ].join(" ")
      }
    >
      {children}
    </NavLink>
  );
}
