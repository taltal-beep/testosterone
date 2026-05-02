import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ComparePage } from "./ComparePage";

describe("ComparePage", () => {
  it("renders comparison data for selected runs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/runs")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              items: [
                { run_id: "run-2", created_at: 2, returncode: 1, status: "FAILED", health_pct: 90, links_under_static: {} },
                { run_id: "run-1", created_at: 1, returncode: 0, status: "COMPLETED", health_pct: 99, links_under_static: {} }
              ]
            })
          });
        }
        if (url.includes("/api/v1/analytics/delta")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              comparison: {
                current_run_id: "run-2",
                baseline_run_id: "run-1",
                current_test_kind: "pytest",
                baseline_test_kind: "pytest"
              },
              metrics: {
                reliability: {
                  total_tests: _metric("improvement", 120, 100, 20, 20, "higher_is_better", "tests"),
                  passed: _metric("improvement", 100, 95, 5, 5.26, "higher_is_better", "tests"),
                  failed: _metric("regression", 8, 2, 6, 300, "lower_is_better", "tests"),
                  broken: _metric("neutral", 0, 0, 0, null, "lower_is_better", "tests"),
                  skipped: _metric("neutral", 1, 1, 0, 0, "lower_is_better", "tests"),
                  health_pct: _metric("regression", 92, 98, -6, -6.12, "higher_is_better", "pct")
                },
                performance: {
                  wall_duration_ms: _metric("regression", 1300, 1100, 200, 18.18, "lower_is_better", "ms"),
                  metrics_duration_ms: _metric("regression", 1200, 1000, 200, 20, "lower_is_better", "ms"),
                  avg_case_ms: _metric("regression", 10.4, 8.9, 1.5, 16.85, "lower_is_better", "ms")
                }
              },
              status_summary: {
                regressions: ["failed", "health_pct", "wall_duration_ms", "metrics_duration_ms", "avg_case_ms"],
                improvements: ["total_tests", "passed"],
                unchanged: ["broken", "skipped"],
                unknown: []
              },
              highlights: ["Failed tests worsened by 6 tests."]
            })
          });
        }
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      })
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/compare"]}>
          <Routes>
            <Route path="/compare" element={<ComparePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText("Run Comparison")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Current run"), { target: { value: "run-2" } });
    fireEvent.change(screen.getByLabelText("Baseline run"), { target: { value: "run-1" } });

    await waitFor(() =>
      expect(
        screen.getByText((_, element) => element?.textContent?.includes("Comparing run-2 against baseline run-1.") ?? false, {
          selector: "p"
        })
      ).toBeInTheDocument()
    );
    expect(screen.getByText(/regressions=5 improvements=2 unchanged=2 unknown=0/)).toBeInTheDocument();
    expect(screen.getByText("Failed tests worsened by 6 tests.")).toBeInTheDocument();
  });
});

function _metric(
  classification: "regression" | "improvement" | "neutral" | "unknown",
  current_value: number | null,
  baseline_value: number | null,
  absolute_delta: number | null,
  relative_delta_pct: number | null,
  direction: "higher_is_better" | "lower_is_better",
  unit: "tests" | "pct" | "ms"
) {
  return {
    current_value,
    baseline_value,
    absolute_delta,
    relative_delta_pct,
    classification,
    reason: null,
    direction,
    unit
  };
}

