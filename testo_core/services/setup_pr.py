"""Put the files ``testo init`` wrote on a branch and open a pull request (``testo init --pr``).

Only git and the GitHub CLI are used, as child processes with fixed argv, so
sign-in, GitHub Enterprise hosts and tokens stay ``gh``'s job (as for
``testo try --from-github``). Only the files ``init`` wrote are committed
(``git commit -- <paths>``), so anything else the user had staged stays
staged and out of the commit.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

SETUP_BRANCH = "testosterone-setup"
COMMIT_MESSAGE = "ci: add Testosterone"
PR_TITLE = "Add Testosterone test history"


def pr_body(cycle: str, files: Sequence[str]) -> str:
    listed = "\n".join(f"- `{f}`" for f in files)
    return (
        "Adds [Testosterone](https://github.com/taltal-beep/testosterone) with `testo init`:\n\n"
        f"{listed}\n\n"
        f"The workflow runs the `{cycle}` cycle on every push and pull request, writes the "
        "results to the job summary and keeps one comment on each pull request with what "
        "broke, what's flaky and what got slower.\n\n"
        "This pull request's own comment has nothing to compare with yet. Once it is merged "
        "and the workflow has run on the default branch, later pull requests are compared "
        "with that run.\n"
    )


@dataclass
class SetupPrResult:
    branch: str
    url: str | None = None
    # Shell commands left for the user to run (no gh, or a step that failed).
    todo: list[str] = field(default_factory=list)
    error: str | None = None


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _free_branch(repo: Path, wanted: str) -> str:
    """*wanted*, or *wanted*-2, -3... when a local branch has that name already."""
    name, n = wanted, 1
    while _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0:
        n += 1
        name = f"{wanted}-{n}"
    return name


def open_setup_pr(
    repo: Path, *, files: Sequence[str], base: str, cycle: str, branch: str = SETUP_BRANCH
) -> SetupPrResult:
    """Commit *files* (paths relative to *repo*) on a new branch, push it and open a pull request."""
    if _git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return SetupPrResult(branch=branch, error=f"{repo} is not a git repository")
    branch = _free_branch(repo, branch)
    title_arg = PR_TITLE.replace("'", "")
    manual = [
        f"git switch -c {branch}",
        f"git add {' '.join(files)}",
        f"git commit -m '{COMMIT_MESSAGE}' -- {' '.join(files)}",
        f"git push -u origin {branch}",
        f"gh pr create --base {base} --head {branch} --title '{title_arg}' --fill",
    ]

    switched = _git(repo, "switch", "-c", branch)
    if switched.returncode != 0:
        return SetupPrResult(branch=branch, todo=manual, error=switched.stderr.strip())
    added = _git(repo, "add", "--", *files)
    committed = (
        _git(repo, "commit", "-m", COMMIT_MESSAGE, "--", *files) if added.returncode == 0 else added
    )
    if committed.returncode != 0:
        return SetupPrResult(
            branch=branch, todo=manual[1:], error=(committed.stderr or committed.stdout).strip()
        )
    if _git(repo, "remote", "get-url", "origin").returncode != 0:
        return SetupPrResult(
            branch=branch,
            todo=manual[3:],
            error="no `origin` remote to push to; add one, then run these",
        )
    pushed = _git(repo, "push", "-u", "origin", branch)
    if pushed.returncode != 0:
        return SetupPrResult(branch=branch, todo=manual[3:], error=pushed.stderr.strip())
    if shutil.which("gh") is None:
        return SetupPrResult(
            branch=branch,
            todo=manual[4:],
            error="the GitHub CLI (https://cli.github.com) isn't installed, so open the pull "
            "request yourself",
        )
    created = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [  # noqa: S607
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            PR_TITLE,
            "--body",
            pr_body(cycle, files),
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if created.returncode != 0:
        return SetupPrResult(branch=branch, todo=manual[4:], error=created.stderr.strip())
    url = next(
        (ln.strip() for ln in created.stdout.splitlines() if ln.strip().startswith("http")), None
    )
    return SetupPrResult(branch=branch, url=url)


DEPENDABOT_PATH = ".github/dependabot.yml"


def dependabot_yaml() -> str:
    """Weekly updates for the workflow's actions (``actions/checkout``, ``setup-python``...)."""
    return (
        "# Written by `testo init --dependabot`: keeps the GitHub Actions in your workflows\n"
        "# current. `taltal-beep/testosterone@v1` already moves to each 1.x release by itself.\n"
        "version: 2\n"
        "updates:\n"
        "  - package-ecosystem: github-actions\n"
        '    directory: "/"\n'
        "    schedule:\n"
        "      interval: weekly\n"
    )
