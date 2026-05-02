import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { RunDetailPage } from "./RunDetailPage";

describe("RunDetailPage", () => {
  it("renders AI summary card for failed runs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/runs/run-1/reports")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ static_links: {}, artifact_links: [] })
          });
        }
        if (url.endsWith("/api/v1/runs/run-1")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              run: {
                run_id: "run-1",
                test_kind: "pytest",
                returncode: 1,
                created_at: 1,
                started_at: 1,
                finished_at: 2,
                wall_duration_ms: 100,
                health_pct: 80
              }
            })
          });
        }
        if (url.endsWith("/api/v1/runs/run-1/ai-summary")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              schema_version: "v1",
              run_id: "run-1",
              status: "available",
              summary_text: "Likely root cause is a flaky fixture setup.",
              confidence: "medium",
              limitations: [],
              provider: "openai",
              model: "gpt-4o-mini",
              generated_at: 1,
              context_stats: { prompt_chars: 10 },
              error_code: null
            })
          });
        }
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      })
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/runs/run-1"]}>
          <Routes>
            <Route path="/runs/:runId" element={<RunDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText("AI Failure Summary")).toBeInTheDocument());
    expect(screen.getByText("Likely root cause is a flaky fixture setup.")).toBeInTheDocument();
  });
});
