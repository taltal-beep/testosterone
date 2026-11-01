import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { FlakyTestsCard } from "./FlakyTestsCard";

vi.mock("../../lib/static-backend", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/static-backend")>()),
  IS_STATIC_BUILD: true
}));

describe("FlakyTestsCard in the read-only demo", () => {
  it("shows the quarantine badge but no buttons", async () => {
    const item = {
      key: "k",
      name: "test_flaky_route",
      group: "tests.api",
      runs: 4,
      passed: 2,
      failed: 2,
      flips: 3,
      flip_rate: 1,
      last_status: "failed",
      history: ["passed", "failed"],
      owners: [],
      issue_url: null
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          cycle: "fake-api",
          window: 20,
          runs_analyzed: 4,
          tests_analyzed: 2,
          items: [
            { ...item, quarantined: true, quarantine_entry: "test_flaky_route" },
            { ...item, key: "k2", name: "test_other" }
          ]
        })
      })
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><FlakyTestsCard cycle="fake-api" /></MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("Quarantined")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /Quarantine|Release/ })).not.toBeInTheDocument();
  });
});
