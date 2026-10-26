import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResourcesPage } from "./ResourcesPage";

const now = Date.now() / 1000;
const lease = {
  holder: { user: "dana", host: "laptop-7", pid: 42, run_id: "run-1", stage: "flows", worker: "gw0", note: "" },
  taken_at: now - 120,
  heartbeat_at: now - 5,
  expires_at: now + 115,
  ttl_s: 120
};
const pools = {
  pools: [
    {
      name: "flow-vms",
      free: 1,
      waiting: 2,
      items: [
        { item: "vm-01", labels: ["win11"], data: {}, disabled: false, disabled_reason: "", disabled_by: null, lease },
        { item: "vm-02", labels: [], data: {}, disabled: false, disabled_reason: "", disabled_by: null, lease: null },
        { item: "vm-03", labels: [], data: {}, disabled: true, disabled_reason: "on_take failed: exit 1", disabled_by: null, lease: null }
      ]
    }
  ]
};

function renderPage(body: unknown) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") return Promise.resolve({ ok: true, status: 204, json: async () => null });
    void input;
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ResourcesPage />
    </QueryClientProvider>
  );
  return fetchMock;
}

describe("ResourcesPage", () => {
  it("shows each key's state and who holds it", async () => {
    renderPage(pools);

    await waitFor(() => expect(screen.getByText("flow-vms")).toBeInTheDocument());
    expect(screen.getByTestId("pool-summary")).toHaveTextContent("1 free · 1 held of 3 · 2 waiting");
    const [held, free, disabled] = screen.getAllByTestId("resource-key");
    expect(within(held).getByText("Held")).toBeInTheDocument();
    expect(held).toHaveTextContent("dana @laptop-7 · run-1 / flows / gw0 · taken 2m ago");
    expect(within(free).getByText("Free")).toBeInTheDocument();
    expect(within(disabled).getByText("Disabled")).toBeInTheDocument();
    expect(disabled).toHaveTextContent("on_take failed: exit 1");
  });

  it("takes a key back and puts a disabled one back", async () => {
    const fetchMock = renderPage(pools);

    await waitFor(() => expect(screen.getByText("flow-vms")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Take vm-01 back from its holder" }));
    fireEvent.click(screen.getByRole("button", { name: "Put back" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2));
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST").map(([url, init]) => [String(url), init?.body]);
    expect(posts).toContainEqual([expect.stringContaining("/api/v1/resources/items/release"), JSON.stringify({ pool: "flow-vms", item: "vm-01" })]);
    expect(posts).toContainEqual([expect.stringContaining("/api/v1/resources/items/enable"), JSON.stringify({ pool: "flow-vms", item: "vm-03" })]);
  });

  it("explains how to add a pool when there is none", async () => {
    renderPage({ pools: [] });

    await waitFor(() => expect(screen.getByText("No resource pools yet")).toBeInTheDocument());
    expect(screen.getByText(/testo lease run POOL -- your-command/)).toBeInTheDocument();
    expect(screen.getByText("testo lease demo")).toBeInTheDocument();
  });
});
