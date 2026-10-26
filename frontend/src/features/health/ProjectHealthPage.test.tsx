import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectHealthPage } from "./ProjectHealthPage";

const health = {
  scope: null,
  score: 84,
  grade: "B",
  cycles: 2,
  runs_considered: 6,
  tests: 120,
  latest_run_at: 1,
  signals: [
    { key: "passing", name: "Passing tests", score: 95, weight: 30, value: "114 of 120 tests passed", how: "Latest runs." },
    { key: "pyramid", name: "Test pyramid", score: null, weight: 10, value: "No tiered tests yet", how: "Set tier." }
  ],
  by_cycle: [
    { cycle: "web", run_id: "r1", created_at: 1, passed_latest: false, tests: 60, failing: 6, flaky: 1, slower: 0, green_runs: 2, runs: 3, score: 70 },
    { cycle: "api", run_id: "r2", created_at: 1, passed_latest: true, tests: 60, failing: 0, flaky: 0, slower: 0, green_runs: 3, runs: 3, score: 98 }
  ],
  findings: [{ kind: "flaky", cycle: "web", title: "test_checkout", detail: "Flaky: failed 2 of 10 runs.", test_key: "k1", run_id: null }]
};

const skills = {
  items: [
    {
      id: "reliability",
      name: "Why tests are flaky",
      category: "Reliability",
      tagline: "Which tests fail for no reason, and why.",
      summary: "Looks at tests that pass and fail on the same code.",
      checks: ["Flaky tests and how often they flip"],
      reads: ["Flaky tests"],
      default_on: true
    },
    {
      id: "naming",
      name: "Test names and messages",
      category: "Readability",
      tagline: "Can a newcomer tell what broke?",
      summary: "Reads test names like a new teammate.",
      checks: ["Names that describe behaviour"],
      reads: ["Test names"],
      default_on: false
    }
  ]
};

const notGenerated = { scope: null, status: "not_generated", skills: [], stale: false, context_stats: {} };

function stub(aiReady: boolean, generated?: unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    let body: unknown = {};
    if (url.includes("/project-health/skills")) body = skills;
    else if (url.includes("/project-health/ai-review")) body = init?.method === "POST" ? generated : notGenerated;
    else if (url.includes("/project-health")) body = health;
    else if (url.includes("/ai/config/status")) body = { enabled: aiReady, configured: aiReady };
    else if (url.includes("/cycles")) body = { items: [{ name: "web" }, { name: "api" }] };
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/health"]}>
        <ProjectHealthPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return fetchMock;
}

afterEach(() => {
  localStorage.clear();
});

describe("ProjectHealthPage", () => {
  it("shows the score, its signals, what to fix and each cycle", async () => {
    stub(false);
    await waitFor(() => expect(screen.getByRole("img", { name: "Test health score: 84 out of 100, grade B" })).toBeInTheDocument());
    expect(screen.getByText("114 of 120 tests passed")).toBeInTheDocument();
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "test_checkout" })).toHaveAttribute("href", expect.stringContaining("/cycles/web/test"));
    expect(screen.getByText("6 failing")).toBeInTheDocument();
  });

  it("lists checks with switches and expandable summaries, and needs AI set up to run", async () => {
    stub(false);
    const row = await screen.findByTestId("skill-naming");
    const toggle = within(row).getByRole("switch", { name: "Test names and messages" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText(/1 of 2 on/)).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(JSON.parse(localStorage.getItem("testo.reviewSkills") ?? "{}")).toEqual({ naming: true });

    expect(screen.queryByText("Reads test names like a new teammate.")).not.toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { expanded: false }));
    expect(screen.getByText("Reads test names like a new teammate.")).toBeInTheDocument();
    expect(within(row).getByText("Names that describe behaviour")).toBeInTheDocument();

    expect(await screen.findByText(/AI is not set up yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run AI review" })).toBeDisabled();
  });

  it("runs the review with the checks that are on and shows the scores", async () => {
    const fetchMock = stub(true, {
      scope: null,
      status: "available",
      score: 72,
      grade: "C",
      summary: "Mostly stable.",
      skills: [{ skill_id: "reliability", name: "Why tests are flaky", score: 72, summary: "One flaky test.", findings: [{ severity: "high", title: "test_checkout flips", detail: "Shared cart state." }] }],
      model: "gemini-2.5-flash",
      generated_at: 1,
      stale: false,
      context_stats: {}
    });
    const button = await screen.findByRole("button", { name: "Run AI review" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByRole("img", { name: "AI review score: 72 out of 100, grade C" })).toBeInTheDocument());
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ cycle: null, skills: ["reliability"] });

    const row = screen.getByTestId("skill-reliability");
    fireEvent.click(within(row).getByRole("button", { expanded: false }));
    expect(within(row).getByText("test_checkout flips")).toBeInTheDocument();
  });
});
