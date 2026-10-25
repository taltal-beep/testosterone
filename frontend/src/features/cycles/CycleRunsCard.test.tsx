import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CycleRunsCard } from "./CycleRunsCard";

function run(run_id: string, cycle: string, created_at: number, returncode: number) {
  return { run_id, cycle, created_at, returncode, status: returncode === 0 ? "COMPLETED" : "FAILED", branch: "main" };
}

describe("CycleRunsCard", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the cycle's pass rate, one square per run oldest first, and links to its runs", async () => {
    const items = [run("w-3", "web", 3, 1), run("api-1", "api", 2.5, 0), run("w-2", "web", 2, 0), run("w-1", "web", 1, 0)];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const cycle = new URL(String(input), "http://x").searchParams.get("cycle");
      return Promise.resolve({ ok: true, json: async () => ({ items: items.filter((i) => !cycle || i.cycle === cycle) }) });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <CycleRunsCard cycle="web" />
        </MemoryRouter>
      </QueryClientProvider>
    );

    const card = await screen.findByTestId("cycle-runs");
    expect(card).toHaveTextContent("Passed 2 of the last 3 runs (67%).");
    const squares = within(screen.getByRole("list", { name: "Outcomes, oldest first" })).getAllByRole("link");
    expect(squares.map((s) => s.getAttribute("href"))).toEqual(["/runs/w-1", "/runs/w-2", "/runs/w-3"]);
    expect(squares[2]).toHaveAccessibleName(/failed$/);
    expect(screen.getByRole("link", { name: "All runs of web" })).toHaveAttribute("href", "/runs?cycle=web");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/runs?cycle=web");
  });
});
