import { NavLink, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <main style={{ fontFamily: "sans-serif", margin: "1rem auto", maxWidth: "900px" }}>
      <h1>Unified Quality Orchestration Dashboard</h1>
      <nav style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        <NavLink to="/">Execution</NavLink>
        <NavLink to="/history">History</NavLink>
      </nav>
      <Outlet />
    </main>
  );
}
