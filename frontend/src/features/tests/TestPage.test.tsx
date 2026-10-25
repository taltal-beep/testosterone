import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TestPage } from "./TestPage";

const TEST = {
  key: "tests/api.py::test_login",
  name: "test_login",
  full_name: "tests.api.test_login",
  group: "tests.api",
  stage: "api",
  runs: 4,
  passed: 3,
  failed: 1,
  last_status: "failed",
  flaky: true,
  last_duration_ms: 400,
  median_duration_ms: 120,
  slowdown_ms: 280,
  slowdown_pct: 233.3
};

function point(runId: string, status: string, createdAt: number, message = "") {
  return { run_id: runId, created_at: createdAt, status, duration_ms: 100, message, branch: "main" };
}

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/cycles/:name/test" element={<TestPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TestPage", () => {
  it("shows the pass rate, last failure and every run", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://localhost");
      expect(url.pathname).toBe("/api/v1/analytics/test-history");
      expect(url.searchParams.get("key")).toBe("tests/api.py::test_login");
      const failure = point("run-4abcdef0", "failed", 4, "AssertionError: 1 != 2");
      return Promise.resolve(
        new Response(
          JSON.stringify({
            cycle: "smoke",
            test: TEST,
            points: [failure, point("run-3", "passed", 3), point("run-2", "passed", 2), point("run-1", "passed", 1)],
            last_failure: failure,
            last_failure_attachments: [
              { name: "screenshot", content_type: "image/png", kind: "image", url: "history/run-4/a-attachment.png", size_bytes: 70 },
              { name: "trace", content_type: "application/zip", kind: "trace", url: "history/run-4/b-attachment.zip", size_bytes: 2048 }
            ],
            owners: ["@org/api"],
            issue_url: "https://github.com/acme/shop/issues/new?title=Flaky+test"
          }),
          { status: 200 }
        )
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt(`/cycles/smoke/test?${new URLSearchParams({ key: TEST.key }).toString()}`);

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("test_login");
    expect(screen.getByText("Passed 3 of 4 runs (75%) in smoke")).toBeInTheDocument();
    expect(screen.getByText("Flaky")).toBeInTheDocument();
    expect(screen.getAllByText("AssertionError: 1 != 2")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Run run-4abc" })).toHaveAttribute("href", "/runs/run-4abcdef0");
    expect(screen.getByText(/Median 120 ms, and 280 ms slower over the last runs \(\+233.3%\)/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Runs (4)" })).toBeInTheDocument();
    // The duration chart reads as text, too.
    expect(screen.getByRole("img", { name: /^Duration per run, oldest first: 100 ms passed, .*, 100 ms failed$/ })).toBeInTheDocument();
    expect(screen.getByText("@org/api")).toBeInTheDocument();
    // What the failing run kept: the screenshot in place, the trace to download.
    expect(screen.getByRole("img", { name: "screenshot from the failing run" })).toHaveAttribute(
      "src",
      expect.stringMatching(/\/history\/run-4\/a-attachment\.png$/)
    );
    expect(screen.getByRole("link", { name: "Download trace" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/history\/run-4\/b-attachment\.zip$/)
    );
    expect(screen.getByText("2 KB")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open an issue" })).toHaveAttribute(
      "href",
      "https://github.com/acme/shop/issues/new?title=Flaky+test"
    );
  });

  it("explains a test that isn't in the recent runs", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("{}", { status: 404 }))));
    renderAt("/cycles/smoke/test?key=gone");
    expect(await screen.findByText(/Couldn't find this test in the recent runs of smoke/)).toBeInTheDocument();
  });
});
