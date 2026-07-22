# Testosterone (testo-core)

Before planning, debugging, or implementing anything in this repo, read [docs/Index.md](docs/Index.md) first — it's the entry point to the Obsidian second-brain vault under `docs/` and links to Architecture, CLI Commands, Release Management, Roadmap & Strategy, and Specs & ADRs notes. For AI-agent-specific conventions (which doc to check before touching what), read [docs/Prompts & Snippets/Agent Context Guide.md](docs/Prompts%20&%20Snippets/Agent%20Context%20Guide.md).

## Quick facts

- Package: `testo-core`. CLI entrypoint: `testo` (Typer). Legacy alias `uqo` is deprecated.
- Config: `testosterone.yaml` at repo root defines cycles/stages/reporters.
- Engine flow: `config/loader.py` → `config/resolver.py` → `engine/orchestrator.run_plan()` → `engine/executor.run_stage()`.
- Framework adapters: `testo_core/frameworks/` (Pytest, Behave, BehaveX).
- API: `testo_api/` (FastAPI, `/api/v1/`). Frontend: `frontend/` (Vite + React + Tailwind). Legacy UI: `testo_ui/` (Streamlit).

## Rules

- **Behave features must be explicitly targeted** (`behave features/smoke.feature`), never rely on cwd auto-discovery. Applies to CLI wrappers, CI, Dockerfiles, adapters.
- If a change alters CLI args, exit codes, or `testosterone.yaml` parsing, update the matching `docs/` note in the same change.
- Code review runs as a local pre-push hook (`.claude/settings.json`), not in CI.

## Commands

```bash
testo run --cycle sample-pytests
testo report --cycle sample-pytests
pytest -q -m "tier_fast and not quarantined" --no-cov
ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full setup and pre-PR checklist.
