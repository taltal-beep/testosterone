import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

function renderShell() {
  const page = (name: string) => <h1>{name} page</h1>;
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: page("Dashboard") },
          { path: "cycles", element: page("Cycles") },
          { path: "quick-run", element: page("Quick Run") }
        ]
      }
    ],
    { initialEntries: ["/"] }
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

describe("AppShell mobile menu", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 404, json: async () => ({}) })));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("toggles a disclosure panel with every nav link", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("navigation", { name: "Main" });
    expect(toggle).toHaveAttribute("aria-controls", panel.id);
    const labels = within(panel)
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(labels).toEqual(["Dashboard", "Cycles", "Runs", "Compare", "Quick Run", "AI Settings"]);

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("closes after navigating", async () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(toggle);
    const panel = screen.getByRole("navigation", { name: "Main" });

    fireEvent.click(within(panel).getByRole("link", { name: "Quick Run" }));

    expect(await screen.findByRole("heading", { name: "Quick Run page" })).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the toggle", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(toggle);
    within(screen.getByRole("navigation", { name: "Main" }))
      .getByRole("link", { name: "Cycles" })
      .focus();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
  });

  it("closes on a click outside the panel", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(toggle);

    fireEvent.mouseDown(screen.getByRole("heading", { name: "Dashboard page" }));

    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
