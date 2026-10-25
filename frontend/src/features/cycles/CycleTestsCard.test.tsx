import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CycleTestsCard } from "./CycleTestsCard";

function item(name: string, overrides: Record<string, unknown> = {}) {
  return {
    key: `k-${name}`,
    name,
    full_name: `tests.api.${name}`,
    group: "tests.api",
    stage: "api",
    runs: 5,
    passed: 5,
    failed: 0,
    last_status: "passed",
    flaky: false,
    last_duration_ms: 10,
    median_duration_ms: 10,
    slowdown_ms: null,
    slowdown_pct: null,
    ...overrides
  };
}

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CycleTestsCard cycle="smoke" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CycleTestsCard", () => {
  it("lists the slowest tests, the ones that got slower, and finds a test by name", async () => {
    const items = [
      item("test_fast"),
      item("test_slow", { median_duration_ms: 2500 }),
      item("test_creeping", { median_duration_ms: 300, slowdown_ms: 200, slowdown_pct: 100 }),
      item("test_login", { last_status: "failed", flaky: true })
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify({ cycle: "smoke", runs_considered: 5, items }), { status: 200 })))
    );
    renderCard();

    expect(await screen.findByRole("heading", { name: "Tests (4)" })).toBeInTheDocument();
    const slowest = screen.getByRole("heading", { name: "Slowest tests" }).nextElementSibling as HTMLElement;
    expect(within(slowest).getAllByRole("link").map((a) => a.textContent)).toEqual([
      "test_slow",
      "test_creeping",
      "test_fast",
      "test_login"
    ]);
    const slower = screen.getByRole("heading", { name: "Got slower" }).nextElementSibling as HTMLElement;
    expect(within(slower).getByRole("link", { name: "test_creeping" })).toHaveAttribute(
      "href",
      "/cycles/smoke/test?key=k-test_creeping"
    );
    expect(within(slower).getByText("+200 ms (+100%)")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Find a test"), { target: { value: "LOGIN" } });
    const results = screen.getByRole("list", { name: "Matching tests" });
    expect(within(results).getByRole("link", { name: "test_login" })).toBeInTheDocument();
    expect(within(results).getByText("Flaky")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Find a test"), { target: { value: "nothing" } });
    expect(screen.getByText('No test matches "nothing".')).toBeInTheDocument();
  });
});
