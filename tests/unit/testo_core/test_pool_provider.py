"""``testo pool status`` and the read-only provider (testo_core/resources/provider.py)."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from testo_core.cli.app import app
from testo_core.config.errors import ConfigValidationError
from testo_core.resources.pools import parse_pool
from testo_core.resources.provider import list_keys, pool_report

REPO_ROOT = Path(__file__).resolve().parents[3]


def _py(code: str) -> str:
    return f'"{sys.executable}" -c "{code}"'


def _lister(*keys: str) -> str:
    return _py("print(" + repr("\n".join(keys)) + ")")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'history.db'}")
    for name in ("TESTO_SERVER_URL", "TESTO_LEASE_DB_URL", "TESTO_RESOURCE_SPEC"):
        monkeypatch.delenv(name, raising=False)
    from testo_core.repository.db_config import reset_engine_cache

    reset_engine_cache()
    return tmp_path


def _write(project: Path, pool: dict[str, object]) -> None:
    (project / "testosterone.yaml").write_text(
        json.dumps({"resources": {"vms": pool}}), encoding="utf-8"
    )


def test_provider_accepts_only_list() -> None:
    pool = parse_pool("vms", {"items": ["vm-1"], "provider": {"list": "ls"}})
    assert pool.provider is not None and pool.provider.list == "ls"
    with pytest.raises(ConfigValidationError, match=r"unknown key\(s\) \['create'\]"):
        parse_pool("vms", {"items": ["vm-1"], "provider": {"create": "make-vm"}})


def test_provider_never_travels_to_a_server_or_a_stage() -> None:
    pool = parse_pool("vms", {"items": ["vm-1"], "provider": {"list": "ls"}})
    assert "provider" not in pool.to_json()
    assert "provider" not in pool.to_json(hooks=False)


def test_list_skips_blank_lines_comments_and_repeats() -> None:
    pool = parse_pool(
        "vms", {"items": ["vm-1"], "provider": {"list": _lister("# header", "vm-1", "", "vm-1")}}
    )
    assert list_keys(pool).keys == ("vm-1",)


def test_report_finds_missing_extra_and_failed_checks() -> None:
    pool = parse_pool(
        "vms",
        {
            "items": ["vm-1", "vm-2", "vm-3"],
            "provider": {"list": _lister("vm-1", "vm-3", "testo-old-9")},
            # vm-3 fails its check.
            "on_check": _py("import os, sys; sys.exit(os.environ['TESTO_RESOURCE_ID'] == 'vm-3')"),
        },
    )
    report = pool_report(pool, check=True)
    assert report.missing == ("vm-2",)
    assert report.extra == ("testo-old-9",)
    assert report.failed_checks == ("vm-3",)
    by_key = {k.key: k for k in report.keys}
    assert by_key["vm-1"].check == ""
    assert by_key["vm-2"].check_skipped  # not listed, so not checked
    assert not report.healthy


def test_a_failing_list_command_is_reported_not_guessed() -> None:
    pool = parse_pool(
        "vms", {"items": ["vm-1"], "provider": {"list": _py("import sys; sys.exit(2)")}}
    )
    report = pool_report(pool)
    assert report.list_problem and "exit 2" in report.list_problem
    assert report.keys[0].exists is None


def test_status_cli_skips_held_keys_and_exits_by_health(project: Path) -> None:
    _write(
        project,
        {
            "items": ["vm-1", "vm-2"],
            "provider": {"list": _lister("vm-1", "vm-2")},
            "on_check": _py("import sys; sys.exit(0)"),
        },
    )
    runner = CliRunner()
    taken = runner.invoke(app, ["lease", "take", "vms", "--json", "--ttl", "1h"])
    assert taken.exit_code == 0, taken.output

    result = runner.invoke(app, ["pool", "status", "--check", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)[0]
    assert report["healthy"] is True
    states = {k["key"]: (k["state"], k["check"]) for k in report["keys"]}
    assert states == {"vm-1": ("held", "skipped: someone holds it"), "vm-2": ("free", "")}

    _write(project, {"items": ["vm-1", "vm-2"], "provider": {"list": _lister("vm-1")}})
    drift = runner.invoke(app, ["pool", "status", "vms"])
    assert drift.exit_code == 1
    assert "missing" in drift.stdout and "never creates or deletes" in drift.stdout

    _write(project, {"items": ["vm-1"], "provider": {"list": _py("import sys; sys.exit(5)")}})
    assert runner.invoke(app, ["pool", "status"]).exit_code == 3
    assert runner.invoke(app, ["pool", "status", "nope"]).exit_code == 2


def test_only_the_pool_command_runs_provider_code() -> None:
    """Leases, runs, stages and the API must never reach the provider (the 'never on its own' rule)."""
    importers = set()
    for root in ("testo_core", "testo_api"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                elif isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                if any(n == "testo_core.resources.provider" for n in names):
                    importers.add(path.relative_to(REPO_ROOT).as_posix())
    assert importers == {"testo_core/cli/commands/pool.py"}
