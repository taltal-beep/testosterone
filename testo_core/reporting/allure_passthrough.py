"""Take Allure result files as they are: ``testo ingest allure-results/``.

Runners with an Allure adapter (allure-jest, allure-junit5, allure-testng,
allure-rspec, allure-cucumber, Allure.NUnit, ...) already write the format
Testosterone stores. Each ``*-result.json`` is copied into the stage's results
with the attachments it names (screenshots, logs, steps' attachments), taken
from the same folder only. The folder's other files (``*-container.json``,
``environment.properties``, ``categories.json``, ``executor.json``) are left
out without a warning; fixtures in containers are not shown.
"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any

_SIDE_FILES = frozenset({"environment.properties", "categories.json", "executor.json"})


# Allure adapters name attachments ``<uuid>-attachment.<ext>`` (or ``<uuid>-attachment``).
_ATTACHMENT = re.compile(r"^.+-attachment(\.[A-Za-z0-9]+)*$")


def is_allure_side_file(path: Path) -> bool:
    """An Allure results folder's file that is not a test result (skipped quietly).

    Only Allure's own names: ``my-attachment-tests.xml`` is still read as a report.
    """
    name = path.name
    if name.endswith("-container.json") or _ATTACHMENT.match(name) or name in _SIDE_FILES:
        return True
    # environment.xml is Allure's only inside an Allure results folder.
    return name == "environment.xml" and any(path.parent.glob("*-result.json"))


def is_allure_result(path: Path, data: Any) -> bool:
    return (
        path.name.endswith("-result.json")
        and isinstance(data, dict)
        and isinstance(data.get("status"), str)
        and bool(data.get("name") or data.get("fullName"))
    )


def _sources(node: dict[str, Any]) -> list[dict[str, Any]]:
    found = [a for a in node.get("attachments") or [] if isinstance(a, dict)]
    for step in node.get("steps") or []:
        if isinstance(step, dict):
            found += _sources(step)
    return found


def copy_allure_result(
    path: Path, data: dict[str, Any], *, results_dir: Path, tool: str
) -> tuple[dict[str, Any], int]:
    """``data`` ready to write to ``results_dir``, and how many attachments were copied there."""
    result = dict(data)
    result["uuid"] = str(uuid.uuid4())
    start = result.get("start")
    if not isinstance(start, int):
        start = int(path.stat().st_mtime * 1000)
        result["start"] = start
    if not isinstance(result.get("stop"), int) or result["stop"] < start:
        result["stop"] = start
    labels = [lab for lab in result.get("labels") or [] if isinstance(lab, dict)]
    if not any(lab.get("name") == "framework" for lab in labels):
        labels.append({"name": "framework", "value": "allure"})
    result["labels"] = labels
    if not result.get("historyId"):
        result["historyId"] = f"{tool}:{result.get('fullName') or result.get('name')}"

    folder = path.parent.resolve()
    copied = 0
    for attachment in _sources(result):
        source = str(attachment.get("source") or "")
        # Only a plain file name, in the result's own folder.
        if not source or Path(source).name != source:
            continue
        candidate = folder / source
        target = results_dir / source
        # A symlink pointing out of the folder (``x-attachment.txt -> /etc/hostname``) would
        # copy that file into the run's artifacts; only files really inside it count.
        if folder not in candidate.resolve().parents:
            continue
        if candidate.is_file() and not target.exists():
            shutil.copyfile(candidate, target)
            copied += 1
    return result, copied
