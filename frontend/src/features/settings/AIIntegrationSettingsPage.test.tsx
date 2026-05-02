import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AIIntegrationSettingsPage } from "./AIIntegrationSettingsPage";

describe("AIIntegrationSettingsPage", () => {
  it("renders config status and saves runtime token settings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/ai/config/status")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              enabled: false,
              configured: false,
              provider: "openai",
              model: "gpt-4o-mini",
              api_key_source: "runtime_input",
              api_key_env_var: null,
              key_present: false,
              timeout_s: 8,
              retry_count: 1,
              max_input_chars: 16000,
              max_output_tokens: 300
            })
          });
        }
        if (url.endsWith("/api/v1/ai/config") && init?.method === "PUT") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              enabled: true,
              configured: true,
              provider: "openai",
              model: "gpt-4o-mini",
              api_key_source: "runtime_input",
              api_key_env_var: null,
              key_present: true,
              timeout_s: 8,
              retry_count: 1,
              max_input_chars: 16000,
              max_output_tokens: 300
            })
          });
        }
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      })
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <AIIntegrationSettingsPage />
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText("AI Integration Settings")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.change(screen.getByPlaceholderText("Enter token (not persisted to disk)"), { target: { value: "sk-temp" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(screen.getByText("Settings saved.")).toBeInTheDocument());
  });
});
