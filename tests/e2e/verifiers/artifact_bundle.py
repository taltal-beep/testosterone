from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_json_artifact(root: Path, category: str, name: str, payload: dict[str, Any]) -> Path:
    bucket = root / category
    bucket.mkdir(parents=True, exist_ok=True)
    out = bucket / f"{name}.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out


def write_text_artifact(root: Path, category: str, name: str, content: str) -> Path:
    bucket = root / category
    bucket.mkdir(parents=True, exist_ok=True)
    out = bucket / f"{name}.log"
    out.write_text(content, encoding="utf-8")
    return out


def assert_artifact_content_redacted(content: str) -> None:
    secret_candidates = [
        os.getenv("UQO_E2E_GITHUB_TOKEN", ""),
        os.getenv("UQO_E2E_GITLAB_TOKEN", ""),
    ]
    for candidate in secret_candidates:
        if candidate and candidate in content:
            raise AssertionError("sensitive token content found in artifact output")

