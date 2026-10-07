import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HistoryPage } from "./HistoryPage";

function run(run_id: string, cycle: string, created_at: number) {
  return { run_id, cycle, created_at, status: "COMPLETED", returncode: 0, health_pct: 100 };
}

function renderWithRuns(items: ReturnType<typeof run>[]) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items }) }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("HistoryPage", () => {
  it("compares the latest run with the previous run of the same cycle", async () => {
    renderWithRuns([run("a-2", "a", 3), run("b-1", "b", 2), run("a-1", "a", 1)]);

    await waitFor(() => expect(screen.getByRole("button", { name: "Compare latest two" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Compare latest two" })).toHaveAttribute(
      "href",
      "/compare?current_run_id=a-2&baseline_run_id=a-1"
    );
  });

  it("hides the compare button when the latest cycle has no earlier run", async () => {
    renderWithRuns([run("a-1", "a", 2), run("b-1", "b", 1)]);

    await waitFor(() => expect(screen.getByText("Runs")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Compare latest two" })).not.toBeInTheDocument();
  });
});
