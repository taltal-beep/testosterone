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
              equipment: ["pytest"],
              source: "config"
            },
            {
              name: "sample-all-frameworks",
              description: "Run pytest, native Behave, then BehaveX.",
              stage_count: 3,
              equipment: ["behave", "behavex", "pytest"],
              source: "config"
            },
            {
              name: "web",
              description: "Recorded runs only.",
              stage_count: 1,
              equipment: ["junit"],
              source: "history"
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
    // The recorded-only cycle opens like the others but has nothing to run.
    expect(screen.getByRole("link", { name: "web" })).toHaveAttribute("href", "/cycles/web");
    expect(screen.getByText("Recorded")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Run" })).toHaveLength(2);
    expect(screen.getByText(/Defined in \/repo\/testosterone.yaml/)).toBeInTheDocument();
  });

  it("says what to check when cycles can't be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) })
    );

    renderPage();

    await waitFor(() => expect(screen.getByText("Couldn't load cycles")).toBeInTheDocument());
    expect(screen.getByText(/testo config validate/)).toBeInTheDocument();
  });

  it("points at testo ingest when there are no cycles at all", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], config_path: null }) })
    );

    renderPage();

    await waitFor(() => expect(screen.getByText("No cycles yet")).toBeInTheDocument());
    expect(screen.getByText(/testo ingest/)).toBeInTheDocument();
  });
});
