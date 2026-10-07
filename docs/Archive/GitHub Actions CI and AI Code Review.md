---
type: archive
status: archived
created: 2026-06-24
updated: 2026-10-07
---

# GitHub Actions CI and AI Code Review

> Archived 2026-10-07. This page existed only in the GitHub wiki (written 2026-06-24) and was moved here before the wiki started being generated from `docs/`. Workflow names, secrets (`UQO_E2E_*`) and the `claude-cr.yml` review job describe the repo as it was then; for current CI see [CI-CD Pipeline Setup](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md).

This page documents the repository's own GitHub Actions workflows under `.github/workflows/` — the **CI** (automated test gates) and the **CR** (AI code review). For the *consumer-facing* CI wrappers shipped as products (the `uqo` GitHub Action / GitLab template, ghost mode, runner images), see [CI-CD Pipeline Setup](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md).

## Workflow overview

| Workflow | File | Trigger | Purpose | Gating |
|----------|------|---------|---------|--------|
| Claude AI Code Review | `claude-cr.yml` | PR `opened`/`synchronize`/`reopened`/`ready_for_review` | AI review posting inline comments | Non-blocking (advisory) |
| pr-fast | `pr-fast.yml` | every PR | Fast required test suite | **Required** |
| pr-heavy | `pr-heavy.yml` | `e2e-heavy` label or manual dispatch | Heavy optional E2E suite | Optional |
| nightly-external | `nightly-external.yml` | cron `0 2 * * *` + manual | External lifecycle E2E | Scheduled |
| release-gate | `release-gate.yml` | manual dispatch | External release gate | Release |

---

## CR — Claude AI Code Review (`claude-cr.yml`)

Automatically reviews every pull request and posts inline review comments using Anthropic's official [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action). No `@claude` mention is required — the absence of a `trigger_phrase` makes it run on all matching PR events.

### How it works
1. PR is opened or updated → workflow triggers.
2. The action authenticates with a **Claude Pro/Max subscription** (OAuth token), checks out the diff, and runs Claude Code in agent review mode (`track_progress: true`).
3. Claude reads the diff and posts a tracking comment plus inline comments on specific lines.

### Review focus (prompt)
In priority order, the reviewer is instructed to flag:
1. Correctness / logic errors and edge cases.
2. Security flaws (injection, unsafe subprocess/shell use, secrets in code, unsafe deserialization, path traversal, SSRF).
3. Performance bottlenecks and resource leaks.
4. Missing or weak test coverage, mapped to the repo's `tier_fast` / `tier_heavy` / `tier_external` markers.

Pure stylistic formatting is explicitly out of scope.

### Required setup
Add the repository secret **`CLAUDE_CODE_OAUTH_TOKEN`** (Settings → Secrets and variables → Actions). Generate it on a machine logged into a paid Claude subscription:

```bash
claude setup-token
```

Copy the resulting `sk-ant-oat...` token into the secret. `GITHUB_TOKEN` is auto-provided by GitHub.

> **Billing note:** the Anthropic **API Console** (pay-as-you-go `ANTHROPIC_API_KEY`) and a **Claude Pro/Max subscription** are *separate wallets*. This workflow intentionally uses the subscription via OAuth, so it consumes no API credits. Using an API key against a $0 console balance fails instantly with a `401` and no posted review.

### Key configuration
```yaml
permissions:
  contents: read
  pull-requests: write
  id-token: write            # required by the action for progress tracking

with:
  claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
  github_token: ${{ secrets.GITHUB_TOKEN }}
  track_progress: true
  claude_args: |
    --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)"
    --max-turns 25
```

Two settings are essential for comments to actually appear:
- **`--allowedTools` must include `mcp__github_inline_comment__create_inline_comment`** — without it Claude has no way to post and the run ends with `No buffered inline comments`.
- **`--max-turns`** must be high enough to finish (a budget of 8 was exhausted before completion; 25 is comfortable for typical PRs).

### Cost / noise guards
- Skips draft PRs and `dependabot[bot]`.
- `concurrency` cancels an in-progress review when the PR is pushed again.
- Reviews are **advisory** — they post comments but do not block merges.

### Troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| Job green, no comment posted | Missing comment tool in `--allowedTools` | Add `mcp__github_inline_comment__create_inline_comment` |
| `error_max_turns` in logs | `--max-turns` too low | Raise the budget |
| `401 Invalid bearer token` | Bad/partial OAuth token | Re-run `claude setup-token`, re-set the secret |
| `is_error: true`, `total_cost_usd: 0`, ~instant | API key with $0 console balance | Switch to `claude_code_oauth_token` (subscription) |
| Need the exact error | Output hidden for security | Temporarily add `show_full_output: true`, re-run, then remove |

---

## CI — Test gates

Tier selection is marker-driven (`pytest -m`) and shared with local and GitLab runs. See [CI-CD Pipeline Setup](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md) for the full tier command reference.

### pr-fast (`pr-fast.yml`) — required
Runs on **every PR** (all target branches), 12-minute timeout, Python 3.11.
```bash
python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1 --no-cov
```
This is the required gate for merging.

### pr-heavy (`pr-heavy.yml`) — optional
Runs only when a PR is labeled **`e2e-heavy`** or via manual `workflow_dispatch`. 30-minute timeout.
```bash
python -m pytest -q -m "tier_heavy and not tier_external" --maxfail=1 --durations=25
```

### nightly-external (`nightly-external.yml`) — scheduled
Cron `0 2 * * *` (daily 02:00 UTC) plus manual dispatch. Runs the external lifecycle suite against real GitHub/GitLab targets. Uses the `external-e2e` concurrency group (no cancel-in-progress) so external runs never overlap.
```bash
python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50
```
Requires the `UQO_E2E_*` secrets (GitHub/GitLab tokens, owner/group, base URL).

### release-gate (`release-gate.yml`) — release
Manual `workflow_dispatch` only, 45-minute timeout. Same external suite as nightly, run as a deliberate pre-release gate. Shares the `external-e2e` concurrency group.

### Shared conventions
- All test jobs upload diagnostics artifacts on failure (or always, for external suites): `.artifacts/e2e/**`, `**/*.log`, summary JSON, API responses, and screenshots when present.
- External suites are isolated under the `external-e2e` concurrency group.

---

## Secrets reference

| Secret | Used by | Purpose |
|--------|---------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude-cr.yml` | Claude subscription auth for AI review |
| `GITHUB_TOKEN` | all | Auto-provided by GitHub Actions |
| `UQO_E2E_GITHUB_TOKEN` / `UQO_E2E_GITHUB_OWNER` | nightly-external, release-gate | External GitHub E2E target |
| `UQO_E2E_GITLAB_TOKEN` / `UQO_E2E_GITLAB_GROUP_ID` / `UQO_E2E_GITLAB_BASE_URL` | nightly-external, release-gate | External GitLab E2E target |

---
**Context & Links:**
- [CI-CD Pipeline Setup](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md) — consumer-facing CI wrappers, ghost mode, runner images
- [QA Strategies](../Testing%20Workflows/QA%20Strategies.md), [E2E Harness Operations Guide](../Processes%20&%20Guides/E2E%20Harness%20Operations%20Guide.md), [Command Reference](../CLI%20Commands/Command%20Reference.md)
- [Troubleshooting and Error Codes](../CLI%20Commands/Troubleshooting%20and%20Error%20Codes.md)
