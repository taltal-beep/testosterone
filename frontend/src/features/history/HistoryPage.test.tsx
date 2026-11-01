import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HistoryPage } from "./HistoryPage";

function run(run_id: string, cycle: string, created_at: number) {
  return { run_id, cycle, created_at, status: "COMPLETED", returncode: 0, health_pct: 100 };
}

function renderWithRuns(items: ReturnType<typeof run>[], path = "/runs") {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/cycles")) {
      const names = [...new Set(items.map((item) => item.cycle))];
      return Promise.resolve({ ok: true, json: async () => ({ items: names.map((name) => ({ name, stage_count: 1 })) }) });
    }
    const cycle = new URL(url, "http://x").searchParams.get("cycle");
    // Like the API: ?cycle= keeps that cycle's runs.
    return Promise.resolve({ ok: true, json: async () => ({ items: items.filter((i) => !cycle || i.cycle === cycle) }) });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <HistoryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("HistoryPage", () => {
  it("compares the latest run with the previous run of the same cycle", async () => {
    renderWithRuns([run("a-2", "a", 3), run("b-1", "b", 2), run("a-1", "a", 1)]);

    await waitFor(() => expect(screen.getByRole("link", { name: "Compare latest two" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Compare latest two" })).toHaveAttribute(
      "href",
      "/compare?current_run_id=a-2&baseline_run_id=a-1"
    );
  });

  it("hides the compare button when the latest cycle has no earlier run", async () => {
    renderWithRuns([run("a-1", "a", 2), run("b-1", "b", 1)]);

    await waitFor(() => expect(screen.getByText("Runs")).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Compare latest two" })).not.toBeInTheDocument();
  });

  it("filters to one cycle and says how often it passed", async () => {
    const failed = { ...run("a-2", "a", 3), returncode: 1, status: "FAILED" };
    renderWithRuns([failed, run("b-1", "b", 2), run("a-1", "a", 1)], "/runs?cycle=a");

    await waitFor(() => expect(screen.getByTestId("pass-rate")).toHaveTextContent("Passed 1 of the last 2 runs (50%)."));
    expect(screen.getByText("Runs of a, newest first.")).toBeInTheDocument();
    expect(screen.queryByText(/^b ·/)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Cycle"), { target: { value: "" } });
    await waitFor(() => expect(screen.getByText("Every recorded run, newest first.")).toBeInTheDocument());
    expect(screen.queryByTestId("pass-rate")).not.toBeInTheDocument();
  });
});

describe("HistoryPage paging", () => {
  it("reaches runs older than the first page", async () => {
    const many = Array.from({ length: 45 }, (_, n) => run(`r-${n}`, "a", 100 - n));
    renderWithRuns(many);

    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(30));
    fireEvent.click(screen.getByRole("button", { name: "Show older runs" }));
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(45));
    expect(screen.queryByRole("button", { name: "Show older runs" })).not.toBeInTheDocument();
  });
});
