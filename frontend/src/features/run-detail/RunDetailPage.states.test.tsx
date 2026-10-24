import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunDetailPage } from "./RunDetailPage";

type RouteMap = Record<string, unknown>;

const RUN = {
  run_id: "run-1",
  test_kind: "cycle",
  cycle: "smoke",
  returncode: 1,
  created_at: 1,
  started_at: 1,
  finished_at: 2,
  wall_duration_ms: 1234,
  health_pct: 50,
  stage_health: [
    { name: "unit", framework: "pytest", total_tests: 4, passed: 4, health_pct: 100 },
    { name: "ui", framework: "behavex", total_tests: 2, passed: 0, health_pct: 0 }
  ]
};

const REPORTS = { static_links: { "Allure report": "history/run-1/allure/index.html" }, artifact_links: ["artifacts/smoke/run.log"] };
const PYRAMID = { unit: 4, integration: 0, e2e: 2, shape: "pyramid", message: "Healthy" };

function summary(overrides: Record<string, unknown>) {
  return {
    schema_version: "v1",
    run_id: "run-1",
    status: "not_available",
    summary_text: null,
    confidence: null,
    limitations: [],
    provider: null,
    model: null,
    generated_at: null,
    context_stats: {},
    error_code: "summary_not_available",
    ...overrides
  };
}

// Answers GETs from `routes` (by path suffix) and lets a test override POSTs.
function stubApi(routes: RouteMap, onPost?: (url: string) => Response | Promise<Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "POST" && onPost) return Promise.resolve(onPost(url));
    const key = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((suffix) => url.endsWith(suffix));
    if (key === undefined) return Promise.resolve(new Response("{}", { status: 404 }));
    const body = routes[key];
    if (body instanceof Response) return Promise.resolve(body);
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path = "/runs/run-1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function defaultRoutes(overrides: RouteMap = {}): RouteMap {
  return {
    "/api/v1/runs/run-1": { run: RUN },
    "/api/v1/runs/run-1/reports": REPORTS,
    "/api/v1/runs/run-1/pyramid": PYRAMID,
    "/api/v1/runs/run-1/ai-summary": summary({}),
    ...overrides
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RunDetailPage states", () => {
  it("shows an error when the run cannot be loaded", async () => {
    stubApi(defaultRoutes({ "/api/v1/runs/run-1": new Response("{}", { status: 500 }) }));
    renderAt();
    expect(await screen.findByText("Failed to load run details.")).toBeInTheDocument();
  });

  it("lists stage health, report links and artifacts on demand", async () => {
    stubApi(defaultRoutes());
    renderAt();

    expect(await screen.findByText("Allure report")).toHaveAttribute(
      "href",
      expect.stringMatching(/\/history\/run-1\/allure\/index\.html$/)
    );
    expect(screen.getByText("4/4")).toBeInTheDocument();
    expect(screen.getByText("0/2")).toBeInTheDocument();
    expect(screen.getByText("1234 ms")).toBeInTheDocument();

    expect(screen.queryByText("artifacts/smoke/run.log")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Artifacts/ }));
    expect(screen.getByText("artifacts/smoke/run.log")).toBeInTheDocument();
  });

  it("shows empty states when a run has no reports or stage breakdown", async () => {
    stubApi(
      defaultRoutes({
        "/api/v1/runs/run-1": { run: { ...RUN, stage_health: [] } },
        "/api/v1/runs/run-1/reports": { static_links: {}, artifact_links: [] },
        "/api/v1/runs/run-1/pyramid": new Response("{}", { status: 500 })
      })
    );
    renderAt();
    expect(await screen.findByText("No reports for this run.")).toBeInTheDocument();
    expect(screen.getByText("Per-stage breakdown not available for this run.")).toBeInTheDocument();
    expect(await screen.findByText("Failed to load test pyramid.")).toBeInTheDocument();
  });

  it("says the AI summary only applies to failed runs on a passed run", async () => {
    stubApi(defaultRoutes({ "/api/v1/runs/run-1": { run: { ...RUN, returncode: 0 } } }));
    renderAt();
    expect(await screen.findByText("Summary only applies to failed runs.")).toBeInTheDocument();
  });

  it("renders the labelled summary sections", async () => {
    stubApi(
      defaultRoutes({
        "/api/v1/runs/run-1/ai-summary": summary({
          status: "available",
          error_code: null,
          summary_text: "What failed: ui login\nLikely cause: stale selector\nNext steps: update the page object",
          confidence: "high",
          model: "gemini-2.5-flash"
        })
      })
    );
    renderAt();
    expect(await screen.findByText("Likely cause:")).toBeInTheDocument();
    expect(screen.getByText(/stale selector/)).toBeInTheDocument();
    expect(screen.getByText(/Confidence: high \| Model: gemini-2.5-flash/)).toBeInTheDocument();
  });

  it("links to AI settings when the provider is misconfigured", async () => {
    stubApi(defaultRoutes({ "/api/v1/runs/run-1/ai-summary": summary({ error_code: "provider_misconfigured" }) }));
    renderAt();
    expect(await screen.findByText(/the AI provider has no API key/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open AI settings" })).toHaveAttribute("href", "/settings/ai");
  });

  it("shows the API's message when generating a summary fails", async () => {
    stubApi(defaultRoutes(), () =>
      new Response(JSON.stringify({ error: { code: "provider_timeout", message: "AI provider timed out." } }), {
        status: 503
      })
    );
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "Generate AI Summary" }));
    await waitFor(() => expect(screen.getByText("AI provider timed out.")).toBeInTheDocument());
  });
});
