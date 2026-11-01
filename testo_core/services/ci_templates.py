"""CI files for a project, from what :mod:`testo_core.services.project_setup` detected.

``testo init`` writes these, and the setup snippets in the docs are rendered
from the same functions, so the two can't drift apart. The output is plain
text (not dumped YAML) so its comments and key order read the way a person
would write them.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from testo_core.services.project_setup import ProjectFacts, Stack

GITHUB_WORKFLOW_PATH = ".github/workflows/testosterone.yml"
ACTION_REF = "taltal-beep/testosterone@v1"


def default_branch(repo: Path) -> str:
    """The checkout's default branch (``origin/HEAD``), else its current branch, else ``main``."""
    for argv in (
        ["git", "-C", str(repo), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ["git", "-C", str(repo), "branch", "--show-current"],
    ):
        try:
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
                argv, check=False, capture_output=True, text=True, timeout=15
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        name = proc.stdout.strip().removeprefix("origin/")
        if proc.returncode == 0 and name:
            return name
    return "main"


def _q(value: str) -> str:
    """A YAML double-quoted scalar (JSON strings are valid YAML)."""
    return json.dumps(value)


def _languages(stacks: tuple[Stack, ...]) -> list[str]:
    seen: list[str] = []
    for stack in stacks:
        if stack.language not in seen:
            seen.append(stack.language)
    return seen


def _install_lines(stacks: tuple[Stack, ...], language: str) -> list[str]:
    lines: list[str] = []
    for stack in stacks:
        if stack.language != language:
            continue
        for cmd in stack.install:
            if cmd not in lines:
                lines.append(cmd)
    return lines


def _github_setup(facts: ProjectFacts, language: str) -> list[str]:
    """``steps:`` entries (already indented 6 spaces) that set up *language* and its dependencies."""
    out: list[str] = []
    installs = _install_lines(facts.stacks, language)
    if language == "python":
        out += [
            "      - uses: actions/setup-python@v5",
            "        with:",
            f"          python-version: {_q(facts.python_version)}",
        ]
    elif language == "node":
        manager = facts.node_package_manager
        if manager == "pnpm":
            out.append("      - uses: pnpm/action-setup@v4")
        if manager == "bun":
            out.append("      - uses: oven-sh/setup-bun@v2")
        out += ["      - uses: actions/setup-node@v4", "        with:"]
        if facts.node_version_file:
            out.append(f"          node-version-file: {facts.node_version_file}")
        else:
            out.append('          node-version: "22"')
        if manager in ("npm", "yarn", "pnpm"):
            out.append(f"          cache: {manager}")
    elif language == "go":
        out += ["      - uses: actions/setup-go@v5", "        with:"]
        out.append(
            f"          go-version-file: {facts.go_version_file}"
            if facts.go_version_file
            else '          go-version: "stable"'
        )
    elif language == "dotnet":
        out += [
            "      - uses: actions/setup-dotnet@v4",
            "        with:",
            f"          dotnet-version: {_q(facts.dotnet_version)}",
        ]
    elif language == "java":
        out += [
            "      - uses: actions/setup-java@v4",
            "        with:",
            "          distribution: temurin",
            '          java-version: "21"',
        ]
        if facts.java_build:
            out.append(f"          cache: {facts.java_build}")
    elif language == "ruby":
        out += [
            "      - uses: ruby/setup-ruby@v1",
            "        with:",
            "          bundler-cache: true",
        ]
        installs = [c for c in installs if c != "bundle install"]  # bundler-cache installs
    elif language == "php":
        out += [
            "      - uses: shivammathur/setup-php@v2",
            "        with:",
            '          php-version: "8.3"',
        ]
    for cmd in installs:
        out.append(f"      - run: {cmd}")
    return out


def github_workflow(facts: ProjectFacts, *, cycle: str, branch: str = "main") -> str:
    """``.github/workflows/testosterone.yml``: set up the stacks, then run *cycle* with the Action."""
    names = ", ".join(s.label for s in facts.stacks) or "your tests"
    lines = [
        f"# Written by `testo init`. Runs the {_q(cycle)} cycle from testosterone.yaml ({names})",
        "# and comments on each pull request with what broke, what's flaky and what got slower.",
        "# Docs: https://taltal-beep.github.io/testosterone/docs/",
        "name: Testosterone",
        "on:",
        "  push:",
        f"    branches: [{_q(branch)}]",
        "  pull_request:",
        "permissions:",
        "  contents: read",
        "  pull-requests: write  # the pull request comment",
        "jobs:",
        "  tests:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v4",
    ]
    for language in _languages(facts.stacks):
        lines += _github_setup(facts, language)
    lines += [
        f"      - uses: {ACTION_REF}",
        "        with:",
        f"          cycle: {_q(cycle)}",
        '          comment-on-pr: "true"',
    ]
    if "python" in _languages(facts.stacks):
        # The Action installs testo into this Python, so pytest sees the project's packages.
        lines.append(f"          python-version: {_q(facts.python_version)}")
    return "\n".join(lines) + "\n"
