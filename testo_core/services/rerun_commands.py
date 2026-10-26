"""A command that reruns a run's failing tests, per runner, for the run page's "Rerun these".

Built from what the run recorded: each failing test's stage, that stage's
framework, and the test's names. Only runners whose command can name single
tests are covered: pytest (node ids), Playwright (``--grep`` on titles) and
Behave (``--name``). JUnit files ingested from other runners get a pytest
command when their names point at a Python test module; anything else is left
out rather than guessed.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass

from testo_core.services.test_ownership import source_path

# A command line people paste stays readable; past this, rerun the stage.
MAX_TESTS = 30
# Regex metacharacters, the same in Python (Behave) and JavaScript (Playwright).
_REGEX_SPECIAL = re.compile(r"[.*+?^${}()|\[\]\\/]")


@dataclass(frozen=True)
class FailingCase:
    name: str
    full_name: str
    group: str
    stage: str


def pytest_node_id(full_name: str, name: str, group: str = "") -> str | None:
    """``tests/api/test_orders.py::TestX::test_y`` from Allure or JUnit names, if they point at a module."""
    if "::" in full_name:
        return full_name
    path = source_path(full_name, group)
    if path is None or not path.endswith(".py"):
        return None
    module = path[: -len(".py")].replace("/", ".")
    dotted = full_name.replace("#", ".")
    rest = dotted[len(module) + 1 :] if dotted.startswith(module + ".") else name
    return f"{path}::{'::'.join(part for part in rest.split('.') if part)}"


def _pytest(cases: list[FailingCase]) -> str | None:
    ids = [pytest_node_id(c.full_name, c.name, c.group) for c in cases]
    if not ids or any(i is None for i in ids):
        return None
    return shlex.join(["pytest", *dict.fromkeys(i for i in ids if i)])


def _literal(text: str) -> str:
    """``text`` as a regex that matches it exactly, readable (spaces stay spaces)."""
    return _REGEX_SPECIAL.sub(lambda m: "\\" + m.group(0), text)


def _grep(titles: Iterable[str]) -> str:
    return "|".join(_literal(t) for t in dict.fromkeys(titles))


def _playwright(cases: list[FailingCase]) -> str:
    return shlex.join(["npx", "playwright", "test", "--grep", _grep(c.name for c in cases)])


def _behave(cases: list[FailingCase], command: str) -> str:
    args = [command]
    for name in dict.fromkeys(c.name for c in cases):
        args += ["--name", f"^{_literal(name)}$"]
    return shlex.join(args)


def rerun_commands(cases: list[FailingCase], frameworks: dict[str, str]) -> list[str]:
    """One command per runner that can rerun ``cases``; ``frameworks`` maps stage name to framework."""
    if not cases or len(cases) > MAX_TESTS:
        return []
    by_framework: dict[str, list[FailingCase]] = {}
    for case in cases:
        framework = frameworks.get(case.stage, "")
        if framework in ("junit", "command", ""):
            # Ingested or wrapped: a Python test module is still a pytest test.
            framework = "pytest" if pytest_node_id(case.full_name, case.name, case.group) else ""
        by_framework.setdefault(framework, []).append(case)
    commands: list[str] = []
    for framework, group in by_framework.items():
        if framework == "pytest":
            command = _pytest(group)
        elif framework == "playwright":
            command = _playwright(group)
        elif framework in ("behave", "behavex"):
            command = _behave(group, framework)
        else:
            command = None
        if command:
            commands.append(command)
    return commands
