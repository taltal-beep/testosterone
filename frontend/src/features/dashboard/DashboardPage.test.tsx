import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "../../app/AppShell";
import { DashboardPage, trendSemantic } from "./DashboardPage";

describe("DashboardPage", () => {
  it("renders overview cards and quick links", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/dashboard/overview")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
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
              data_freshness: { generated_at: 1, source_window_size: 2, degraded: false, notes: [] }
            })
          });
        }
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      })
    );

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

    await waitFor(() => expect(screen.getByText("Dashboard Overview")).toBeInTheDocument());
    expect(screen.getByTestId("health-trend")).toHaveTextContent("Trend: improved");
    expect(screen.getByRole("link", { name: "Latest run details" })).toHaveAttribute("href", "/runs/run-1");
    expect(screen.getByRole("link", { name: "Compare latest two runs" })).toHaveAttribute(
      "href",
      "/compare?current_run_id=run-1&baseline_run_id=run-0"
    );
  });

  it("renders degraded and empty states", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({
            headline_kpis: {
              latest_run_id: null,
              latest_status: null,
              health_pct: null,
              pass_count: null,
              fail_count: null,
              duration_ms: null
            },
            trend_indicators: {
              health: { direction: "unknown", delta_abs: null, delta_pct: null },
              failed_count: { direction: "unknown", delta_abs: null, delta_pct: null },
              duration: { direction: "unknown", delta_abs: null, delta_pct: null }
            },
            reliability_rollup: {
              status_summary: { regressions: 0, improvements: 0, unchanged: 0, unknown: 0 },
              top_highlights: []
            },
            performance_rollup: {
              status_summary: { regressions: 0, improvements: 0, unchanged: 0, unknown: 0 },
              top_highlights: []
            },
            report_links: {
              allure: { url: null, state: "unknown" },
              locust: { url: null, state: "missing" },
              behave: { url: null, state: "missing" }
            },
            recent_runs: [],
            data_freshness: { generated_at: 1, source_window_size: 0, degraded: true, notes: ["no_runs_available"] }
          })
        })
      )
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DashboardPage />
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText(/Some metrics are degraded:/)).toBeInTheDocument());
    expect(screen.getByText("No recent runs available.")).toBeInTheDocument();
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
