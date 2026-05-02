import { FormEvent, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient, UpdateAiConfigRequest } from "../../lib/api-client";

export function AIIntegrationSettingsPage() {
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");

  const statusQuery = useQuery({
    queryKey: ["ai-config-status"],
    queryFn: () => apiClient.getAiConfigStatus()
  });

  const status = statusQuery.data;
  const [formState, setFormState] = useState<UpdateAiConfigRequest>({
    enabled: false,
    provider: "openai",
    model: "gpt-4o-mini",
    api_key_source: "env",
    api_key_env_var: null,
    timeout_s: 8,
    retry_count: 1,
    max_input_chars: 16000,
    max_output_tokens: 300
  });

  useEffect(() => {
    if (!status) {
      return;
    }
    setFormState({
      enabled: status.enabled,
      provider: status.provider,
      model: status.model,
      api_key_source: status.api_key_source,
      api_key_env_var: status.api_key_env_var,
      timeout_s: status.timeout_s,
      retry_count: status.retry_count,
      max_input_chars: status.max_input_chars,
      max_output_tokens: status.max_output_tokens
    });
  }, [status]);

  if (statusQuery.isLoading) {
    return <p>Loading AI settings...</p>;
  }
  if (statusQuery.isError || !status) {
    return <p>Failed to load AI settings.</p>;
  }

  const effectiveForm = formState;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState("saving");
    setSaveError(null);
    try {
      await apiClient.updateAiConfig({
        ...effectiveForm,
        api_key_input: apiKeyInput || undefined
      });
      setApiKeyInput("");
      setSaveState("saved");
      await statusQuery.refetch();
    } catch (error) {
      setSaveState("error");
      setSaveError(error instanceof Error ? error.message : "Failed to save settings.");
    }
  }

  return (
    <section>
      <h2>AI Integration Settings</h2>
      <p>Bring your own key. Tokens are masked and never returned by the API.</p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: "0.75rem", maxWidth: "480px" }}>
        <label>
          <input
            type="checkbox"
            checked={effectiveForm.enabled}
            onChange={(event) => setFormState((prev) => ({ ...prev, enabled: event.target.checked }))}
          />{" "}
          Enable AI failure summaries
        </label>
        <label>
          Provider
          <select
            value={effectiveForm.provider}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, provider: event.target.value as "openai" | "anthropic" }))
            }
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </label>
        <label>
          Model
          <input
            value={effectiveForm.model}
            onChange={(event) => setFormState((prev) => ({ ...prev, model: event.target.value }))}
          />
        </label>
        <label>
          API key source
          <select
            value={effectiveForm.api_key_source}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, api_key_source: event.target.value as "env" | "runtime_input" }))
            }
          >
            <option value="env">Environment variable</option>
            <option value="runtime_input">Runtime input</option>
          </select>
        </label>
        {effectiveForm.api_key_source === "env" ? (
          <label>
            API key env var
            <input
              value={effectiveForm.api_key_env_var ?? ""}
              onChange={(event) => setFormState((prev) => ({ ...prev, api_key_env_var: event.target.value || null }))}
            />
          </label>
        ) : (
          <label>
            API token
            <input
              type="password"
              value={apiKeyInput}
              placeholder="Enter token (not persisted to disk)"
              onChange={(event) => setApiKeyInput(event.target.value)}
            />
          </label>
        )}
        <button type="submit" disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving..." : "Save settings"}
        </button>
      </form>
      <p role="status">
        Status: {status.configured ? "configured" : "not configured"} | Provider: {status.provider} | Model:{" "}
        {status.model}
      </p>
      {saveState === "saved" ? <p>Settings saved.</p> : null}
      {saveState === "error" ? <p>Save failed: {saveError}</p> : null}
    </section>
  );
}
