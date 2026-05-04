# AI Failure Summaries

UQO can generate concise AI explanations for failed runs by sending a bounded, redacted failure context to a configured provider. The feature is optional and additive: it does not change run execution, CLI exit codes, or existing run/history contracts.

## Source map

| Concern | Codepath |
| --- | --- |
| API routes | `uqo_api/routes/ai.py` |
| API schemas | `uqo_api/models.py` (`AiConfig*`, `AiSummaryResponse`) |
| Settings store | `uqo_core/services/ai/integration_settings.py` |
| Provider config/factory | `uqo_core/services/ai/config.py`, `uqo_core/services/ai/factory.py` |
| Provider adapters | `uqo_core/services/ai/providers/openai_provider.py`, `uqo_core/services/ai/providers/anthropic_provider.py` |
| Prompt/context builder | `uqo_core/services/failure_context_builder.py` |
| Summary orchestration | `uqo_core/services/failure_analysis_service.py` |
| React settings page | `frontend/src/features/settings/AIIntegrationSettingsPage.tsx` |
| React run-detail card | `frontend/src/features/run-detail/RunDetailPage.tsx` |

## Configuration model

AI summaries are disabled by default. The current settings store is in-memory per FastAPI process, so runtime-input keys and settings are cleared when the API process restarts.

Supported providers:

- `openai`
  - default model: `gpt-4o-mini`
  - default environment key: `OPENAI_API_KEY`
  - endpoint: `https://api.openai.com/v1/chat/completions`
- `anthropic`
  - default environment key: `ANTHROPIC_API_KEY`
  - endpoint: `https://api.anthropic.com/v1/messages`

Configurable limits:

- `timeout_s` must be greater than `0` (default `8.0`).
- `retry_count` cannot be negative (default `1`; provider adapters currently perform one request).
- `max_input_chars` must be greater than `0` (default `16000`).
- `max_output_tokens` must be greater than `0` (default `300`).

API keys can come from:

- `env`: reads the provider default env var or explicit `api_key_env_var`.
- `runtime_input`: accepts `api_key_input` through `PUT /api/v1/ai/config`; the raw key is retained only in the API process memory and is never returned by status responses.

## API workflow

Check non-secret status:

```bash
curl http://localhost:8000/api/v1/ai/config/status
```

Enable OpenAI with an environment variable:

```bash
export OPENAI_API_KEY=sk-...

curl -X PUT http://localhost:8000/api/v1/ai/config \
  -H 'Content-Type: application/json' \
  -d '{
    "enabled": true,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "api_key_source": "env",
    "timeout_s": 8,
    "retry_count": 1,
    "max_input_chars": 16000,
    "max_output_tokens": 300
  }'
```

Enable Anthropic with runtime input:

```bash
curl -X PUT http://localhost:8000/api/v1/ai/config \
  -H 'Content-Type: application/json' \
  -d '{
    "enabled": true,
    "provider": "anthropic",
    "model": "claude-3-5-haiku-latest",
    "api_key_source": "runtime_input",
    "api_key_input": "sk-ant-...",
    "timeout_s": 8,
    "retry_count": 1,
    "max_input_chars": 16000,
    "max_output_tokens": 300
  }'
```

Read or generate a run summary:

```bash
curl http://localhost:8000/api/v1/runs/<run_id>/ai-summary

curl -X POST http://localhost:8000/api/v1/runs/<run_id>/ai-summary:generate \
  -H 'Content-Type: application/json' \
  -d '{"force_refresh": false}'
```

Set `force_refresh=true` to regenerate an already available summary.

## Summary behavior

`AiSummaryResponse` uses `schema_version="v1"` and one of these statuses:

- `available`: a provider returned summary text. The response includes `summary_text`, `provider`, `model`, `confidence`, `generated_at`, `limitations`, and `context_stats`.
- `no_summary_generated`: no summary text is available. Check `error_code` and `limitations`.

Generation only applies to failed runs. The service returns `no_summary_generated` when:

- the run cannot be found (`run_not_found`)
- the run return code is `0` (`run_not_failed`)
- the AI feature is disabled (`ai_feature_disabled`)
- the provider is misconfigured (`provider_misconfigured`)
- the provider timed out (`provider_timeout`)
- the provider rate-limited the request (`provider_rate_limited`)
- the provider/model pair is rejected (`unsupported_provider_model`)
- the provider fails for another redacted reason (`summary_not_available`)

Generated summaries are stored additively in run metadata under `ai_summary_v1`. Existing summaries are reused unless `force_refresh=true` is requested.

## Context and security constraints

The prompt is built from verified run history fields plus selected metadata:

- run id, test kind, status, return code, failed/broken counts, and health percentage
- `error_message` or `error`
- `traceback`, `stack_trace`, or `audit_json`
- `sync` metadata

Before provider submission, context text is redacted and bounded. Default section budgets are:

- total prompt: `max_input_chars` from config
- failure log: `8000` chars
- trace: `4000` chars
- metadata: `4000` chars

When data is truncated, `limitations` can include `log_truncated`, `trace_truncated`, `metadata_truncated`, or `context_budget_truncated`.

Security guarantees enforced by the current implementation:

- the feature is explicit opt-in (`enabled=false` by default)
- raw API keys are not returned by API responses
- runtime-input keys are memory-only
- token-like values are redacted from failure context and provider error surfaces
- generation failure is reported as a typed summary status, not as a run execution failure

## Frontend workflow

React exposes:

- `/settings/ai`: configure provider, model, key source, and enablement.
- `/runs/:runId`: view the AI failure summary card and trigger generation.

Successful runs show a message that summaries apply only to failed runs. Failed runs show an available summary, a typed no-summary reason, or a loading/error state.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `configured=false` for env keys | Confirm the FastAPI process environment contains `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or the custom `api_key_env_var`. |
| `ai_feature_disabled` | Enable AI through `/settings/ai` or `PUT /api/v1/ai/config`. |
| `provider_misconfigured` | Verify key source and key presence; runtime-input keys disappear after API restart. |
| `provider_timeout` | Increase `timeout_s` or check provider/network availability. |
| `provider_rate_limited` | Check provider quota and retry later. |
| `unsupported_provider_model` | Verify that the configured provider supports the selected model for the supplied key. |
| Summary does not change | Regenerate with `force_refresh=true`. |
| Secret-looking text appears in evidence | Add or update redaction coverage in `uqo_core/security/redaction.py` and `tests/unit/uqo_core/test_redaction.py`. |

## Verification

Focused checks for this subsystem:

```bash
python -m pytest -q --no-cov \
  tests/unit/uqo_core/test_ai_provider_abstraction.py \
  tests/unit/uqo_core/test_ai_config_model.py \
  tests/unit/uqo_core/test_redaction.py \
  tests/unit/uqo_core/test_failure_context_builder.py \
  tests/unit/uqo_core/test_failure_analysis_service.py \
  tests/contract/api/test_ai_contract.py
```
