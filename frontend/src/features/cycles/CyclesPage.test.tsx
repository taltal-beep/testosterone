import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { CyclesPage } from "./CyclesPage";

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <CyclesPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("CyclesPage", () => {
  it("lists cycles with stage counts, equipment badges and run buttons", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              name: "sample-pytests",
              description: "Pytest suite for the sample target repo.",
              stage_count: 1,
              equipment: ["pytest"]
            },
            {
              name: "sample-all-frameworks",
              description: "Run pytest, native Behave, then BehaveX.",
              stage_count: 3,
              equipment: ["behave", "behavex", "pytest"]
            }
          ],
          config_path: "/repo/testosterone.yaml"
        })
      })
    );

    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "sample-pytests" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "sample-pytests" })).toHaveAttribute("href", "/cycles/sample-pytests");
    expect(screen.getByText("3 stages")).toBeInTheDocument();
    expect(screen.getByText("behavex")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Run" })).toHaveLength(2);
    expect(screen.getByText(/Defined in \/repo\/testosterone.yaml/)).toBeInTheDocument();
  });

  it("shows the shrug empty state when no config is found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) })
    );

    renderPage();

    await waitFor(() => expect(screen.getByText("No testosterone.yaml found")).toBeInTheDocument());
    expect(screen.getByText(/testo config init/)).toBeInTheDocument();
  });
});
