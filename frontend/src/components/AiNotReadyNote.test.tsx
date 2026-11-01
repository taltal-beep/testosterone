import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { AiConfigStatus } from "../lib/api-client";
import { AiNotReadyNote } from "./AiNotReadyNote";

function show(status: Partial<AiConfigStatus>) {
  render(
    <MemoryRouter>
      <AiNotReadyNote status={status as AiConfigStatus} />
    </MemoryRouter>
  );
}

describe("AiNotReadyNote", () => {
  it("says switched off, not 'add a provider', when Claude Code is found but disabled", () => {
    show({ provider: "claude_code", configured: true, enabled: false, key_present: null });
    expect(screen.getByText(/AI is switched off/)).toBeInTheDocument();
    expect(screen.queryByText(/not set up yet/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open AI settings" })).toHaveAttribute("href", "/settings/ai");
  });

  it("asks for a provider when none is configured", () => {
    show({ provider: "openai", configured: false, enabled: false });
    expect(screen.getByText(/AI is not set up yet/)).toBeInTheDocument();
  });
});
