"""Fork-safe pull request comments: ``comment-artifact`` and ``post-comments``."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def _wrapper() -> ModuleType:
    script = Path("integrations/github-action/run_testo_action.py").resolve()
    spec = importlib.util.spec_from_file_location("run_testo_action_forks", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pr_event(tmp_path: Path) -> Path:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 9}}))
    return event


def test_comment_artifact_writes_the_comment_instead_of_posting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _wrapper()
    monkeypatch.setattr(module, "render_markdown", lambda **_: "<!-- testo-summary:unit -->\nhi")

    def no_api(*_a: object, **_k: object) -> None:
        raise AssertionError("must not call the API")

    monkeypatch.setattr(module, "_github", no_api)
    output = tmp_path / "out.txt"
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(_pr_event(tmp_path)),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(output),
        "TESTO_GITHUB_TOKEN": "t",
        "TESTO_INPUT_COMMENT_ARTIFACT": "true",
    }

    module.publish_summary(cycle="unit", job_summary=False, comment=True, env=env)

    assert (tmp_path / "testo-comment" / "unit.md").read_text().endswith("hi")
    assert output.read_text() == f"comment_dir={tmp_path / 'testo-comment'}\n"


def test_safe_comment_needs_the_marker_and_defuses_mentions() -> None:
    module = _wrapper()
    assert module.safe_comment("hello @team") is None
    assert module.safe_comment("<!-- testo-summary:x -->\n" + "a" * 70_000) is None
    assert (
        module.safe_comment("<!-- testo-summary:x -->\nping @team")
        == "<!-- testo-summary:x -->\nping &#64;team"
    )


def _workflow_run_env(tmp_path: Path, *, pull_requests: list[dict[str, object]]) -> dict[str, str]:
    event = tmp_path / "wr.json"
    event.write_text(
        json.dumps({"workflow_run": {"head_sha": "abc", "pull_requests": pull_requests}})
    )
    return {
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_REPOSITORY": "o/r",
        "GITHUB_API_URL": "https://api.example",
        "TESTO_GITHUB_TOKEN": "t",
    }


def test_post_comments_finds_the_fork_pull_request_by_its_head_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _wrapper()
    folder = tmp_path / "testo-comment"
    folder.mkdir()
    (folder / "unit.md").write_text("<!-- testo-summary:unit -->\nbody @x")
    (folder / "evil.md").write_text("not ours")
    calls: list[tuple[str, str, object]] = []

    def fake_github(method: str, url: str, token: str, body: object = None) -> object:
        calls.append((method, url, body))
        if "/pulls?" in url:
            return [{"number": 3, "head": {"sha": "zzz"}}, {"number": 4, "head": {"sha": "abc"}}]
        return []

    monkeypatch.setattr(module, "_github", fake_github)
    env = _workflow_run_env(tmp_path, pull_requests=[])

    assert module.post_comments(folder=folder, env=env) == 1
    assert calls[-1] == (
        "POST",
        "https://api.example/repos/o/r/issues/4/comments",
        {"body": "<!-- testo-summary:unit -->\nbody &#64;x"},
    )


def test_post_comments_uses_the_event_pull_request_for_a_branch_of_the_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _wrapper()
    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "unit.md").write_text("<!-- testo-summary:unit -->\nok")
    urls: list[str] = []

    def fake_github(method: str, url: str, token: str, body: object = None) -> object:
        urls.append(url)
        return []

    monkeypatch.setattr(module, "_github", fake_github)
    env = _workflow_run_env(tmp_path, pull_requests=[{"number": 7, "head": {"sha": "abc"}}])

    assert module.post_comments(folder=folder, env=env) == 1
    assert not any("/pulls?" in u for u in urls)
    assert urls[-1].endswith("/issues/7/comments")


def test_post_comments_with_no_matching_pull_request_posts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _wrapper()
    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "unit.md").write_text("<!-- testo-summary:unit -->\nok")
    monkeypatch.setattr(module, "_github", lambda *a, **k: [])
    env = _workflow_run_env(tmp_path, pull_requests=[])

    assert module.post_comments(folder=folder, env=env) == 0


def test_post_comments_with_no_artifact_is_a_quiet_no_op(tmp_path: Path) -> None:
    module = _wrapper()
    env = _workflow_run_env(tmp_path, pull_requests=[])
    assert module.post_comments(folder=tmp_path / "missing", env=env) == 0
