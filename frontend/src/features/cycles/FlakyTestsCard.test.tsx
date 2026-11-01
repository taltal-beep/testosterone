import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { FlakyTestsCard } from "./FlakyTestsCard";

function renderCard(payload: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><FlakyTestsCard cycle="fake-api" /></MemoryRouter>
    </QueryClientProvider>
  );
  return fetchMock;
}

const base = { cycle: "fake-api", window: 20, runs_analyzed: 4, tests_analyzed: 39 };

describe("FlakyTestsCard", () => {
  it("lists flaky tests with their flip count and history", async () => {
    const fetchMock = renderCard({
      ...base,
      items: [
        {
          key: "k",
          name: "test_flaky_route",
          group: "tests.api",
          runs: 4,
          passed: 2,
          failed: 2,
          flips: 3,
          flip_rate: 1,
          last_status: "failed",
          history: ["passed", "failed", "passed", "failed"],
          owners: ["@org/api"],
          issue_url: "https://github.com/acme/shop/issues/new?title=Flaky+test%3A+test_flaky_route"
        }
      ]
    });

    await waitFor(() => expect(screen.getByText("test_flaky_route")).toBeInTheDocument());
    expect(screen.getByText(/owned by @org\/api/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open an issue" })).toHaveAttribute(
      "href",
      expect.stringContaining("github.com/acme/shop/issues/new")
    );
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/analytics/flaky?cycle=fake-api");
    expect(screen.getByText("Flaky tests (1)")).toBeInTheDocument();
    expect(screen.getByText("3 flips in 4 runs")).toBeInTheDocument();
    expect(screen.getByLabelText("History, oldest first: passed, failed, passed, failed")).toBeInTheDocument();
  });

  it("says when nothing is flaky", async () => {
    renderCard({ ...base, items: [] });
    await waitFor(() => expect(screen.getByText("No flaky tests.")).toBeInTheDocument());
  });

  it("asks for more runs when there is too little history", async () => {
    renderCard({ ...base, runs_analyzed: 1, items: [] });
    await waitFor(() => expect(screen.getByText(/Run this cycle a few more times/)).toBeInTheDocument());
  });

  it("shows the first 10 of a long list until asked for all", async () => {
    const items = Array.from({ length: 25 }, (_, n) => ({
      key: `k${n}`,
      name: `test_${n}`,
      group: "g",
      runs: 4,
      passed: 2,
      failed: 2,
      flips: 3,
      flip_rate: 1,
      last_status: "failed",
      history: ["passed", "failed", "passed", "failed"],
      owners: [],
      issue_url: null
    }));
    renderCard({ ...base, items });

    await waitFor(() => expect(screen.getByText("test_9")).toBeInTheDocument());
    expect(screen.queryByText("test_10")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all 25" }));
    expect(screen.getByText("test_24")).toBeInTheDocument();
  });
});
