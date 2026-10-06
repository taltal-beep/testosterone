import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { QuickRunPage } from "./QuickRunPage";

class FakeEventSource {
  private listeners: Record<string, Array<(evt: MessageEvent) => void>> = {};
  onerror: ((evt: Event) => void) | null = null;

  addEventListener(type: string, cb: (evt: MessageEvent) => void) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(cb);
  }

  emit(type: string, data: unknown) {
    const evt = { data: JSON.stringify(data) } as MessageEvent;
    for (const cb of this.listeners[type] || []) {
      cb(evt);
    }
  }

  close() {}
}

describe("QuickRunPage", () => {
  it("posts an ad-hoc execution and follows the cycle event stream", async () => {
    const source = new FakeEventSource();
    vi.stubGlobal("EventSource", vi.fn(() => source));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        execution_id: "adhoc-1",
        status: "queued",
        events_url: "http://localhost:8000/api/v1/cycle-executions/adhoc-1/events",
        summary_url: "http://localhost:8000/api/v1/cycle-executions/adhoc-1"
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <QuickRunPage />
      </MemoryRouter>
    );
    fireEvent.change(screen.getByDisplayValue("pytest"), { target: { value: "behave" } });
    fireEvent.change(screen.getByDisplayValue("-q"), { target: { value: "features/smoke.feature" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(screen.getByText("execution adhoc-1")).toBeInTheDocument());
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/adhoc-executions");
    expect(JSON.parse(String(init.body))).toMatchObject({
      framework: "behave",
      target_repo: ".",
      args: ["features/smoke.feature"],
      persist: true
    });
    expect(EventSource).toHaveBeenCalledWith("http://localhost:8000/api/v1/cycle-executions/adhoc-1/events");

    source.emit("stage_started", { event: "stage_started", stage: "behave", framework: "behave", index: 0, count: 1 });
    source.emit("stage_finished", {
      event: "stage_finished",
      stage: "behave",
      framework: "behave",
      returncode: 0,
      duration_s: 1.5,
      log_path: null,
      timed_out: false
    });
    source.emit("plan_finished", {
      event: "plan_finished",
      plan: "adhoc",
      aggregate_returncode: 0,
      exit_code: 0,
      duration_s: 1.5
    });

    await waitFor(() => expect(screen.getByTestId("run-outcome")).toHaveTextContent("Run passed."));
    expect(screen.getByText("1.5s")).toBeInTheDocument();
  });
});
