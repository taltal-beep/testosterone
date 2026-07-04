import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "../../app/AppShell";
import { DashboardPage, trendSemantic } from "./DashboardPage";

function overviewPayload(overrides: Record<string, unknown> = {}) {
  return {
    headline_kpis: {
      latest_run_id: "run-1",
      latest_status: "COMPLETED",
      health_pct: 98,
      pass_count: 12,
      fail_count: 1,
      duration_ms: 1222
    },
    trend_indicators: {
      health: { direction: "up", delta_abs: 2, delta_pct: 2.1 },
      failed_count: { direction: "down", delta_abs: -1, delta_pct: -50 },
      duration: { direction: "down", delta_abs: -100, delta_pct: -7.5 }
    },
    reliability_rollup: {
      status_summary: { regressions: 1, improvements: 3, unchanged: 2, unknown: 0 },
      top_highlights: ["Failed tests improved by 1 tests."]
    },
    performance_rollup: {
      status_summary: { regressions: 0, improvements: 2, unchanged: 1, unknown: 0 },
      top_highlights: ["Wall duration improved by 100.00 ms."]
    },
    report_links: {
      allure: { url: "http://allure/run-1", state: "available" },
      locust: { url: "/history/run-1/locust_report.html", state: "available" },
      behave: { url: "/history/run-1/allure_reports/behavex/index.html", state: "available" }
    },
    recent_runs: [
      {
        run_id: "run-1",
        created_at: 1,
        status: "COMPLETED",
        returncode: 0,
        health_pct: 98,
        duration_ms: 1222,
        run_detail_url: "/runs/run-1",
        compare_url: "/compare?current_run_id=run-1&baseline_run_id=run-0"
      }
    ],
    data_freshness: { generated_at: 1, source_window_size: 2, degraded: false, notes: [] },
    ...overrides
  };
}

function stubOverviewFetch(payload: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/dashboard/overview")) {
        return Promise.resolve({ ok: true, json: async () => payload });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    })
  );
}

function renderDashboard() {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AppShell />,
        children: [{ index: true, element: <DashboardPage /> }]
      }
    ],
    { initialEntries: ["/"] }
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

describe("DashboardPage", () => {
  it("renders overview cards and quick links", async () => {
    stubOverviewFetch(overviewPayload());
    renderDashboard();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument());
    expect(screen.getByTestId("health-trend")).toHaveTextContent("Trend: improved");
    expect(screen.getByRole("link", { name: "Latest run details" })).toHaveAttribute("href", "/runs/run-1");
    expect(screen.getByRole("link", { name: "Compare latest two runs" })).toHaveAttribute(
      "href",
      "/compare?current_run_id=run-1&baseline_run_id=run-0"
    );
  });

  it("renders the first-run guide when no runs exist", async () => {
    stubOverviewFetch(
      overviewPayload({
        headline_kpis: {
          latest_run_id: null,
          latest_status: null,
          health_pct: null,
          pass_count: null,
          fail_count: null,
          duration_ms: null
        },
        recent_runs: [],
        data_freshness: { generated_at: 1, source_window_size: 0, degraded: true, notes: ["no_runs_available"] }
      })
    );
    renderDashboard();

    await waitFor(() => expect(screen.getByTestId("first-run-guide")).toBeInTheDocument());
    expect(screen.getByText("Welcome to Testo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "see what you have" })).toHaveAttribute("href", "/cycles");
  });

  it("renders degraded notice and unavailable report links when data exists", async () => {
    stubOverviewFetch(
      overviewPayload({
        report_links: {
          allure: { url: null, state: "unknown" },
          locust: { url: null, state: "missing" },
          behave: { url: null, state: "missing" }
        },
        data_freshness: { generated_at: 1, source_window_size: 1, degraded: true, notes: ["single_run_window"] }
      })
    );
    renderDashboard();

    await waitFor(() => expect(screen.getByText(/Some metrics are degraded:/)).toBeInTheDocument());
    expect(screen.getByText("Allure report (state unknown)")).toBeInTheDocument();
    expect(screen.getByText("Locust report (not available)")).toBeInTheDocument();
  });

  it("maps trend semantics correctly", () => {
    expect(trendSemantic({ direction: "up", delta_abs: 1, delta_pct: 1 }, false).label).toBe("improved");
    expect(trendSemantic({ direction: "up", delta_abs: 1, delta_pct: 1 }, true).label).toBe("regressed");
    expect(trendSemantic({ direction: "flat", delta_abs: 0, delta_pct: 0 }, true).label).toBe("flat");
    expect(trendSemantic({ direction: "unknown", delta_abs: null, delta_pct: null }, false).label).toBe("unknown");
  });
});
