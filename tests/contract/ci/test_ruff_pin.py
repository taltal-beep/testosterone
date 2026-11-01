"""CI (the ``dev`` extra) and the pre-commit hook run the same ruff, so a commit
the hook formatted can't fail ``ruff format --check`` in CI."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml


def test_pre_commit_ruff_matches_the_dev_extra_pin() -> None:
    dev = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]["dev"]
    pins = [m.group(1) for d in dev if (m := re.fullmatch(r"ruff==(\S+)", d))]
    assert len(pins) == 1, "pin ruff to one exact version in the dev extra"
    hooks = yaml.safe_load(Path(".pre-commit-config.yaml").read_text(encoding="utf-8"))
    revs = [r["rev"] for r in hooks["repos"] if r["repo"].endswith("/ruff-pre-commit")]
    assert revs == [f"v{pins[0]}"]
