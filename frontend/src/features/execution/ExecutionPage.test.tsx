import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExecutionPage } from "./ExecutionPage";

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

describe("ExecutionPage", () => {
  it("starts execution and renders streamed logs and summary", async () => {
    const source = new FakeEventSource();
    vi.stubGlobal("EventSource", vi.fn(() => source));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          execution_id: "exec-1",
          status: "running",
          events_url: "http://localhost:8000/api/v1/executions/exec-1/events",
          summary_url: "http://localhost:8000/api/v1/executions/exec-1"
        })
      })
    );

    render(<ExecutionPage />);
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(screen.getByText("Execution ID: exec-1")).toBeInTheDocument());

    source.emit("log", { stream: "stdout", line: "hello", ts: 1 });
    source.emit("summary", { exit_code: 0, runs: [] });

    await waitFor(() => expect(screen.getByTestId("log-console")).toHaveTextContent("[stdout] hello"));
    await waitFor(() => expect(screen.getByTestId("summary-json")).toHaveTextContent('"exit_code": 0'));
  });
});
