from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path("action.yml")
SUBFOLDER = Path("integrations/github-action/action.yml")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_root_action_matches_subfolder_action() -> None:
    """The Marketplace copy at the root and the older subfolder path stay the same action."""
    root, sub = _load(ROOT), _load(SUBFOLDER)
    run_step = "integrations/github-action/run_testo_action.py"
    root_text = ROOT.read_text(encoding="utf-8")
    assert f'"$GITHUB_ACTION_PATH/{run_step}"' in root_text
    # Only the script's location differs: the root action reaches into the subfolder.
    for step in root["runs"]["steps"]:
        if "run" in step:
            step["run"] = step["run"].replace(f"/{run_step}", "/run_testo_action.py")
    assert root == sub


def test_root_action_is_ready_for_the_marketplace() -> None:
    root = _load(ROOT)
    assert root["branding"]["icon"] and root["branding"]["color"]
    # Short enough to show in full on the Marketplace card.
    assert len(root["description"]) <= 125


def test_inputs_never_pasted_into_a_shell_script() -> None:
    """``${{ inputs.x }}`` inside ``run:`` is script injection when a caller passes a
    branch name or PR title; inputs go through ``env:`` instead."""
    for path in (ROOT, SUBFOLDER):
        for step in _load(path)["runs"]["steps"]:
            assert "${{" not in step.get("run", ""), (path, step.get("name"))
