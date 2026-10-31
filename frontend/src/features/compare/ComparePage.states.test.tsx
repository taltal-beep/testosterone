import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ComparePage } from "./ComparePage";

const RUNS = {
  items: [
    { run_id: "run-2", cycle: "fake-api", created_at: 2, returncode: 1, status: "FAILED", health_pct: 90, links_under_static: {} },
    { run_id: "run-1", cycle: "fake-api", created_at: 1, returncode: 0, status: "COMPLETED", health_pct: 99, links_under_static: {} }
  ]
};

function metric(current: number, baseline: number) {
  return {
    current_value: current,
    baseline_value: baseline,
    absolute_delta: current - baseline,
    relative_delta_pct: null,
    classification: current === baseline ? "neutral" : "regression",
    reason: null,
    direction: "lower_is_better",
    unit: "tests"
  };
}

const DELTA = {
  comparison: { current_run_id: "run-2", baseline_run_id: "run-1", current_test_kind: "cycle", baseline_test_kind: "cycle" },
  metrics: {
    reliability: {
      total_tests: metric(3, 3),
      passed: metric(2, 3),
      failed: metric(1, 0),
      broken: metric(0, 0),
      skipped: metric(0, 0),
      health_pct: metric(66, 100)
    },
    performance: { wall_duration_ms: metric(10, 10), metrics_duration_ms: metric(10, 10), avg_case_ms: metric(3, 3) }
  },
  status_summary: { regressions: ["failed"], improvements: [], unchanged: [], unknown: [] },
  highlights: []
};

const CASES = {
  current_run_id: "run-2",
  baseline_run_id: "run-1",
  changes: [
    {
      key: "a",
      group: "fake-api/api",
      name: "test_broken",
      kind: "regression",
      baseline_status: "passed",
      current_status: "failed",
      duration_delta_ms: 12
    },
    {
      key: "b",
      group: "fake-api/api",
      name: "test_new",
      kind: "added",
      baseline_status: null,
      current_status: "passed",
      duration_delta_ms: null
    }
  ]
};

type RouteMap = Array<[string, unknown]>;

// Matches by substring, first entry wins, so list the more specific paths first.
function stubApi(routes: RouteMap) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const hit = routes.find(([part]) => url.includes(part));
      if (!hit) return Promise.resolve(new Response("{}", { status: 404 }));
      const body = hit[1];
      return Promise.resolve(body instanceof Response ? body : new Response(JSON.stringify(body), { status: 200 }));
    })
  );
}

function renderAt(path = "/compare") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/compare" element={<ComparePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const PAIR = "/compare?current_run_id=run-2&baseline_run_id=run-1";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ComparePage states", () => {
  it("shows an error when runs cannot be loaded", async () => {
    stubApi([["/api/v1/runs", new Response("{}", { status: 500 })]]);
    renderAt();
    expect(await screen.findByText("Couldn't load runs to compare. Check that the API is running, then reload.")).toBeInTheDocument();
  });

  it("needs at least two runs", async () => {
    stubApi([["/api/v1/runs", { items: RUNS.items.slice(0, 1) }]]);
    renderAt();
    expect(await screen.findByText("At least two completed runs are required for comparison.")).toBeInTheDocument();
  });

  it("opens on the latest run against the one before it, and asks for two different runs", async () => {
    stubApi([
      ["/api/v1/analytics/delta", DELTA],
      ["/api/v1/runs", RUNS]
    ]);
    renderAt();
    await waitFor(() => expect(screen.getByLabelText("Current run")).toHaveValue("run-2"));
    expect(screen.getByLabelText("Baseline run")).toHaveValue("run-1");
    expect(screen.getByLabelText("Cycle")).toHaveValue("fake-api");
    fireEvent.change(screen.getByLabelText("Baseline run"), { target: { value: "run-2" } });
    expect(screen.getByLabelText("Current run")).toHaveValue("run-2");
    expect(screen.getByText("Select two different runs to start comparison.")).toBeInTheDocument();
  });

  it("preselects runs from the URL and shows a delta error", async () => {
    stubApi([
      ["/api/v1/analytics/delta", new Response("{}", { status: 500 })],
      ["/api/v1/runs", RUNS]
    ]);
    renderAt(PAIR);
    expect(await screen.findByText("Couldn't compare these runs. One of them may have been cleaned up.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current run")).toHaveValue("run-2");
    expect(screen.getByLabelText("Baseline run")).toHaveValue("run-1");
  });

  it("loads test-level changes on demand and filters them by kind", async () => {
    stubApi([
      ["/api/v1/analytics/delta/cases", CASES],
      ["/api/v1/analytics/delta", DELTA],
      ["/api/v1/runs", RUNS]
    ]);
    renderAt(PAIR);

    const toggle = await screen.findByRole("button", { name: /Test-level changes/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);

    expect(await screen.findByText("test_broken")).toBeInTheDocument();
    expect(screen.getByText("test_new")).toBeInTheDocument();
    expect(screen.getByText(/passed → failed \(\+12ms\)/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Regression" }));
    expect(screen.getByText("test_broken")).toBeInTheDocument();
    expect(screen.queryByText("test_new")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Removed" }));
    expect(screen.getByText("No matching test changes.")).toBeInTheDocument();
  });
});
