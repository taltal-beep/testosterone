import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AskPage, SUGGESTED_QUESTIONS } from "./AskPage";

function stub(aiReady: boolean, reply: (body: { question: string; history: unknown[] }) => unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    let body: unknown = {};
    if (url.includes("/api/v1/ask")) body = reply(JSON.parse(String(init?.body)));
    else if (url.includes("/ai/config/status")) body = { enabled: aiReady, configured: aiReady };
    else if (url.includes("/cycles")) body = { items: [{ name: "web" }] };
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/ask?cycle=web"]}>
        <AskPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return fetchMock;
}

const answered = (question: string, answer: string) => ({ status: "answered", question, answer, model: "gemini-2.5-flash", context_stats: {} });

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("AskPage", () => {
  it("asks a suggested question, then a follow-up with the conversation so far", async () => {
    const fetchMock = stub(true, (body) =>
      answered(body.question, body.history.length ? "test_pay got 800 ms slower." : "test_checkout broke in the latest run.")
    );
    const suggestion = await screen.findByRole("button", { name: SUGGESTED_QUESTIONS[0] });
    await waitFor(() => expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled());
    fireEvent.click(suggestion);

    expect(await screen.findByText("test_checkout broke in the latest run.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: SUGGESTED_QUESTIONS[0] })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "and what got slower?" } });
    fireEvent.keyDown(screen.getByLabelText("Your question"), { key: "Enter" });
    expect(await screen.findByText("test_pay got 800 ms slower.")).toBeInTheDocument();
    expect(screen.getAllByTestId("ask-turn")).toHaveLength(2);

    const asks = fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/v1/ask"));
    const second = JSON.parse(String(asks[1][1]?.body));
    expect(second).toEqual({
      question: "and what got slower?",
      cycle: "web",
      history: [{ question: SUGGESTED_QUESTIONS[0], answer: "test_checkout broke in the latest run." }]
    });

    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    expect(screen.queryAllByTestId("ask-turn")).toHaveLength(0);
  });

  it("shows the provider's error and keeps the question", async () => {
    stub(true, (body) => ({ status: "failed", question: body.question, error_code: "provider_timeout", error_message: "The AI provider took too long.", context_stats: {} }));
    fireEvent.change(await screen.findByLabelText("Your question"), { target: { value: "anything flaky?" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The AI provider took too long.");
    expect(screen.getByLabelText("Your question")).toHaveValue("anything flaky?");
  });

  it("points to AI settings when no provider is set up", async () => {
    stub(false, () => ({}));
    expect(await screen.findByRole("link", { name: "Open AI settings" })).toHaveAttribute("href", "/settings/ai");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });
});
