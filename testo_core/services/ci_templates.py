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


# Where `testo init --ci <system>` writes, and the file it writes instead when that one
# exists (it never edits a pipeline of yours; it says what to add).
CI_FILES: dict[str, tuple[str, str]] = {
    "github": (GITHUB_WORKFLOW_PATH, GITHUB_WORKFLOW_PATH),
    "gitlab": (".gitlab-ci.yml", ".gitlab/testosterone.gitlab-ci.yml"),
    "jenkins": ("Jenkinsfile", "Jenkinsfile.testosterone"),
    "circleci": (".circleci/config.yml", ".circleci/testosterone.yml"),
}


def detect_ci(repo: Path) -> str | None:
    """The CI system *repo* already uses, if any (GitHub Actions wins when there are several)."""
    if (repo / ".github" / "workflows").is_dir():
        return "github"
    for name, marker in (
        ("gitlab", ".gitlab-ci.yml"),
        ("jenkins", "Jenkinsfile"),
        ("circleci", ".circleci/config.yml"),
    ):
        if (repo / marker).exists():
            return name
    return None


def ci_file_text(system: str, facts: ProjectFacts, *, cycle: str, branch: str) -> str:
    if system == "github":
        return github_workflow(facts, cycle=cycle, branch=branch)
    if system == "gitlab":
        return gitlab_ci(facts, cycle=cycle)
    if system == "jenkins":
        return jenkinsfile(facts, cycle=cycle)
    if system == "circleci":
        return circleci_config(facts, cycle=cycle)
    raise ValueError(f"unknown CI system {system!r}")


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


# --- other CI systems: the project's own test command, then `testo ingest` -------------------

CI_SYSTEMS: tuple[str, ...] = ("github", "gitlab", "jenkins", "circleci")

# Native-equipment stacks run straight from CI with the runner's own result file;
# ``command`` stacks already are a shell command (see project_setup).
_NATIVE_COMMANDS: dict[str, str] = {
    "pytest": "pytest {args} --junitxml=test-results/pytest.xml",
    "jest": "npx jest --ci --json --outputFile=test-results/jest.json",
    "vitest": (
        "npx vitest run --reporter=default --reporter=json --outputFile.json=test-results/vitest.json"
    ),
    "playwright": (
        "PLAYWRIGHT_JSON_OUTPUT_NAME=test-results/playwright.json npx playwright test --reporter=list,json"
    ),
}

# By stack first (a Maven or Gradle image has its build tool), then by language.
GITLAB_IMAGES: dict[str, str] = {
    "maven": "maven:3-eclipse-temurin-21",
    "gradle": "gradle:jdk21",
    "python": "python:{python}",
    "node": "node:22",
    "go": "golang:1.23",
    "dotnet": "mcr.microsoft.com/dotnet/sdk:8.0",
    "java": "eclipse-temurin:21-jdk",
    "ruby": "ruby:3.3",
    "php": "composer:2",
}
CIRCLECI_IMAGES: dict[str, str] = {
    "python": "cimg/python:{python}",
    "node": "cimg/node:lts",
    "go": "cimg/go:1.23",
    "dotnet": "mcr.microsoft.com/dotnet/sdk:8.0",
    "java": "cimg/openjdk:21.0",
    "ruby": "cimg/ruby:3.3",
    "php": "cimg/php:8.3",
}


def ci_test_command(stack: Stack) -> str:
    """The shell command that runs *stack*'s tests in CI and leaves a result file Testosterone reads."""
    import shlex

    args = [str(a) for a in stack.stage.get("args") or []]
    if stack.key in _NATIVE_COMMANDS:
        cmd = _NATIVE_COMMANDS[stack.key].format(args=shlex.join(args)).replace("  ", " ")
    elif args[:2] == ["sh", "-c"] and len(args) == 3:
        return args[2]
    else:
        cmd = shlex.join(args)
    # A runner that writes a file there needs the folder; `--results-directory` creates its own.
    needs_dir = "test-results/" in cmd and "--results-directory" not in cmd
    return f"mkdir -p test-results && {cmd}" if needs_dir else cmd


def _install_and_test(stack: Stack) -> list[str]:
    return [*stack.install, ci_test_command(stack)]


def _image(table: dict[str, str], stack: Stack, facts: ProjectFacts) -> str:
    image = table.get(stack.key) or table[stack.language]
    return image.format(python=facts.python_version)


# Installs testo with uv (a single binary that brings its own Python), so the
# language image needs nothing but curl. An image with Python can use
# `pip install testo-core` instead.
_INSTALL_TESTO = [
    "command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh",
    'export PATH="$HOME/.local/bin:$PATH"',
    "uv tool install --quiet testo-core",
]


def _record(cycle: str, history_dir: str) -> list[str]:
    return [
        *_INSTALL_TESTO,
        f'mkdir -p "{history_dir}"',
        f'export DATABASE_URL="sqlite:///{history_dir}/testo_history.db"',
        f"testo ingest --cycle {cycle}",
        f"testo report markdown --cycle {cycle} --out testo-summary.md",
    ]


def _cycles(facts: ProjectFacts, cycle: str) -> list[tuple[Stack, str]]:
    """One job per stack; with more than one, each records its own cycle (``<cycle>-<stack>``)."""
    if len(facts.stacks) == 1:
        return [(facts.stacks[0], cycle)]
    return [(s, f"{cycle}-{s.key}") for s in facts.stacks]


def zero_config_github_workflow(facts: ProjectFacts, *, cycle: str, branch: str = "main") -> str:
    """A workflow with no ``testosterone.yaml``: the tests as they are, then the Action records them."""
    lines = [
        "name: tests",
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
    for stack in facts.stacks:
        lines.append(f"      - run: {ci_test_command(stack)}")
    lines += [
        f"      - uses: {ACTION_REF}",
        "        if: ${{ !cancelled() }}  # record red runs too",
        "        with:",
        f"          cycle: {_q(cycle)}",
    ]
    return "\n".join(lines) + "\n"


def gitlab_ci(facts: ProjectFacts, *, cycle: str) -> str:
    """``.gitlab-ci.yml`` jobs: run the tests, record them in ``after_script`` (runs on failure too)."""
    lines = [
        "# Testosterone: records each run's results and keeps their history in the GitLab cache.",
        "# Docs: https://taltal-beep.github.io/testosterone/docs/",
        "stages: [test]",
    ]
    for stack, name in _cycles(facts, cycle):
        lines += [
            "",
            f"{stack.key}:",
            "  stage: test",
            f"  image: {_image(GITLAB_IMAGES, stack, facts)}",
            "  cache:",
            f"    key: testo-history-{stack.key}-$CI_COMMIT_REF_SLUG",
            f"    fallback_keys: [testo-history-{stack.key}-$CI_DEFAULT_BRANCH]",
            "    paths: [.testo-history/]",
            "    when: always",
            "  script:",
        ]
        lines += [f"    - {_yaml_cmd(c)}" for c in _install_and_test(stack)]
        lines.append("  after_script:")
        lines += [f"    - {_yaml_cmd(c)}" for c in _record(name, "$CI_PROJECT_DIR/.testo-history")]
        lines += [
            "  artifacts:",
            "    when: always",
            "    paths: [testo-summary.md, test-results/]",
        ]
    return "\n".join(lines) + "\n"


def _yaml_cmd(cmd: str) -> str:
    """A shell command as a YAML list item, single-quoted only when YAML would misread it."""
    special_start = tuple("-?:,[]{}#&*!|>'\"%@`")
    if cmd.startswith(special_start) or ": " in cmd or " #" in cmd or cmd.endswith(":"):
        return "'" + cmd.replace("'", "''") + "'"
    return cmd


def jenkinsfile(facts: ProjectFacts, *, cycle: str) -> str:
    """A declarative ``Jenkinsfile``: a stage per stack, then ``post { always { ... } }`` records them."""

    def sh(cmd: str) -> str:
        return "sh '" + cmd.replace("\\", "\\\\").replace("'", "\\'") + "'"

    lines = [
        "// Testosterone: records each build's results. History lives in the workspace",
        "// (.testo-history); for one history across agents, use a team server",
        "// (testo ingest --server). Docs: https://taltal-beep.github.io/testosterone/docs/",
        "pipeline {",
        "  agent any  // needs the test tools and curl",
        "  stages {",
    ]
    for stack in facts.stacks:
        lines.append(f"    stage('{stack.label}') {{")
        lines.append("      steps {")
        lines += [f"        {sh(c)}" for c in _install_and_test(stack)]
        lines += ["      }", "    }"]
    record = "\n".join(f"          {c}" for c in _record(cycle, "$WORKSPACE/.testo-history"))
    lines += [
        "  }",
        "  post {",
        "    always {",
        "      sh '''",
        record,
        "      '''",
        "      archiveArtifacts artifacts: 'testo-summary.md', allowEmptyArchive: true",
        "    }",
        "  }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def circleci_config(facts: ProjectFacts, *, cycle: str) -> str:
    """``.circleci/config.yml``: a job per stack that runs the tests and records them (``when: always``)."""
    lines = [
        "# Testosterone: records each run's results and keeps their history in the CircleCI cache.",
        "# Docs: https://taltal-beep.github.io/testosterone/docs/",
        "version: 2.1",
        "jobs:",
    ]
    jobs = _cycles(facts, cycle)
    for stack, name in jobs:
        lines += [
            f"  {stack.key}:",
            "    docker:",
            f"      - image: {_image(CIRCLECI_IMAGES, stack, facts)}",
            "    steps:",
            "      - checkout",
            "      - restore_cache:",
            "          keys:",
            f"            - testo-history-{stack.key}-{{{{ .Branch }}}}-",
            f"            - testo-history-{stack.key}-",
        ]
        lines += [f"      - run: {_yaml_cmd(c)}" for c in _install_and_test(stack)]
        lines += [
            "      - run:",
            "          name: Record the results with Testosterone",
            "          when: always",
            "          command: |",
        ]
        lines += [f"            {c}" for c in _record(name, "$HOME/.testo-history")]
        lines += [
            "      - save_cache:",
            "          when: always",
            f"          key: testo-history-{stack.key}-{{{{ .Branch }}}}-{{{{ .BuildNum }}}}",
            "          paths: [~/.testo-history]",
            "      - store_artifacts:",
            "          path: testo-summary.md",
        ]
    lines += ["workflows:", "  tests:", "    jobs:"]
    lines += [f"      - {stack.key}" for stack, _ in jobs]
    return "\n".join(lines) + "\n"
