"""The demo pipeline and the static UI build share a layout; keep them in step.

``scripts/export_static_site.py`` writes JSON at paths that
``frontend/src/lib/static-backend.ts`` reads back. Nothing at runtime couples
them, so these tests pin the few names both sides agree on, plus the pipeline
wiring that makes the published site work (Pages base, SPA fallback, cycles).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PIPELINE = REPO_ROOT / ".gitlab-ci.yml"
EXPORTER = REPO_ROOT / "scripts" / "export_static_site.py"
STATIC_BACKEND = REPO_ROOT / "frontend" / "src" / "lib" / "static-backend.ts"


def _pipeline() -> dict:
    return yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))


def test_pipeline_runs_cycles_then_publishes_pages() -> None:
    payload = _pipeline()
    assert payload["stages"] == ["demo", "deploy"]

    demo = payload["run_demo_cycles"]
    script = "\n".join(demo["script"])
    assert 'testo run --cycle "$TESTO_BASELINE_CYCLE" --ci' in script
    assert 'testo run --cycle "$TESTO_CURRENT_CYCLE" --ci' in script
    assert "scripts/export_static_site.py" in script
    assert "public" in demo["artifacts"]["paths"]

    pages = payload["pages"]
    assert pages["needs"][0]["job"] == "run_demo_cycles"
    assert pages["artifacts"]["paths"] == ["public"]


def test_demo_cycles_exist_in_the_config() -> None:
    variables = _pipeline()["variables"]
    config = yaml.safe_load((REPO_ROOT / "testosterone.yaml").read_text(encoding="utf-8"))
    for key in ("TESTO_BASELINE_CYCLE", "TESTO_CURRENT_CYCLE"):
        assert variables[key] in config["cycles"], f"{key} names a cycle that no longer exists"


def test_pages_job_wires_the_static_build_and_spa_fallback() -> None:
    script = "\n".join(_pipeline()["pages"]["script"])
    # Vite needs the Pages subpath; the shim needs the data directory under it.
    assert "VITE_BASE=" in script
    assert "VITE_STATIC_DATA_BASE=" in script
    assert "VITE_API_BASE_URL=" in script
    # GitLab Pages serves 404.html for unknown paths, which is how deep links survive a refresh.
    assert "cp public/index.html public/404.html" in script


def test_exporter_and_frontend_shim_agree_on_the_file_layout() -> None:
    exporter = EXPORTER.read_text(encoding="utf-8")
    shim = STATIC_BACKEND.read_text(encoding="utf-8")
    for name in (
        "manifest.json",
        "health.json",
        "ai-config.json",
        "cycles.json",
        "runs.json",
        "dashboard/overview.json",
        "dashboard/recent-runs.json",
        "comparison.json",
        "cases.json",
        "detail.json",
    ):
        assert name in exporter, f"exporter no longer writes {name}"
        assert name in shim, f"the static backend no longer reads {name}"

    # The per-run extras are one file per endpoint name on both sides.
    for name in ("reports", "pyramid", "ai-summary"):
        assert f"{name}.json" in exporter, f"exporter no longer writes {name}.json"
        assert name in shim, f"the static backend no longer maps /{name}"
