---
type: archive
status: archived
created: 2026-06-25
updated: 2026-10-07
---

# AI Prompt Engineering Lab

> **Rule:** Do not store historical AI outputs or chat logs here. Only store reusable prompt templates.

<!-- source: notion https://www.notion.so/354d95cd0312800899a6db0e65446e30 -->

This vault holds **reusable prompt templates** for the Testo project (`testo-core`). Each block below is a copy-paste starting point—a "Mega-Prompt" you can drop into Cursor or another AI assistant when starting a recurring task.

Before adding templates, read the [Agent Context Guide](../Prompts%20&%20Snippets/Agent%20Context%20Guide.md) for vault navigation rules. Prompts here should respect CLI contracts in [Command Reference](../CLI%20Commands/Command%20Reference.md) and execution patterns in [QA Strategies](../Testing%20Workflows/QA%20Strategies.md).

## How to use

1. Find the category that matches your task.
2. Copy the prompt inside the `text` code block (or replace the placeholder with your proven prompt).
3. Fill in any `{placeholders}` before sending.
4. When a prompt proves successful, paste it back into the matching block and give the subsection a descriptive title.

---

## Documentation Generation

### Template: Update docs after a code change

```text
<!-- Paste your mega-prompt here -->
```

### Template: Architecture note from source code

```text
<!-- Paste your mega-prompt here -->
```

---

## Code Refactoring

### Template: Safe refactor with backward compatibility

```text
<!-- Paste your mega-prompt here -->
```

### Template: Reduce duplication (DRY / SOLID)

```text
<!-- Paste your mega-prompt here -->
```

---

## Testing & QA

### Template: Add or extend unit tests

```text
<!-- Paste your mega-prompt here -->
```

### Template: E2E / cycle validation

```text
<!-- Paste your mega-prompt here -->
```

---

## CLI & Architecture

### Template: New or changed CLI command

```text
<!-- Paste your mega-prompt here -->
```

### Template: Execution lifecycle / adapter change

```text
<!-- Paste your mega-prompt here -->
```

---

## CI/CD & Release

### Template: Pipeline or runner integration

```text
<!-- Paste your mega-prompt here -->
```

### Template: Release checklist walkthrough

```text
<!-- Paste your mega-prompt here -->
```

---

## Debugging & Troubleshooting

### Template: NDJSON / exit-code investigation

```text
<!-- Paste your mega-prompt here -->
```

### Template: Artifact or report pipeline debug

```text
<!-- Paste your mega-prompt here -->
```

---

## Related

- [Agent Context Guide](../Prompts%20&%20Snippets/Agent%20Context%20Guide.md) — master map for AI agents
- [Command Reference](../CLI%20Commands/Command%20Reference.md) — CLI contracts prompts should respect
- [QA Strategies](../Testing%20Workflows/QA%20Strategies.md) — how runs are triggered and logged
- [CI-CD Pipeline Setup](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md) — CI wrapper patterns
- [Technical Debt Tracker](../Testing%20Workflows/Technical%20Debt%20Tracker.md) — code-level backlog (not prompt drafts)

---
**Context & Links:** [UQO Engineering Hub](UQO%20Engineering%20Hub.md), [Index](../Index.md)
