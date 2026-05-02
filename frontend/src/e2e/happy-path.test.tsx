import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "../app/AppShell";
import { HistoryPage } from "../features/history/HistoryPage";
import { RunDetailPage } from "../features/run-detail/RunDetailPage";

describe("happy path", () => {
  it("loads history and opens run details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/runs")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              items: [
                {
                  run_id: "run-1",
                  created_at: 1,
                  returncode: 0,
                  status: "COMPLETED",
                  health_pct: 100,
                  links_under_static: {}
                }
              ]
            })
          });
        }
        if (url.endsWith("/api/v1/runs/run-1")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              run: {
                run_id: "run-1",
                test_kind: "pytest",
                returncode: 0,
                created_at: 1,
                started_at: 1,
                finished_at: 2,
                wall_duration_ms: 1000,
                health_pct: 100
              }
            })
          });
        }
        if (url.endsWith("/api/v1/runs/run-1/reports")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              static_links: { pytest: "history/run-1/index.html" },
              artifact_links: ["allure_report.html"]
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
          children: [
            { path: "/history", element: <HistoryPage /> },
            { path: "/runs/:runId", element: <RunDetailPage /> }
          ]
        }
      ],
      {
        initialEntries: ["/history"]
      }
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText("run-1")).toBeInTheDocument());
    await router.navigate("/runs/run-1");
    await waitFor(() => expect(screen.getByText("Run ID: run-1")).toBeInTheDocument());
    expect(screen.getByText("allure_report.html")).toBeInTheDocument();
  });
});
