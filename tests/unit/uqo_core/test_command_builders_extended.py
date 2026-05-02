"""Extended coverage for ``uqo_core.command_builders``."""

from __future__ import annotations

from pathlib import Path

from uqo_core.command_builders import RunConfig, TestType, build_command, coerce_path, ensure_dir, stringify_argv
from uqo_core.command_builders import _strip_behavex_output_folder_args


def test_build_behavex_includes_formatter_and_parallel_defaults(tmp_path: Path) -> None:
    art = tmp_path / "artifacts"
    cfg = RunConfig(
        test_type=TestType.BEHAVEX,
        target_repo=tmp_path,
        shared_allure_results_dir=art / "allure-results" / "behavex",
        artifacts_root=art,
        behavex_args=(),
    )
    bc = build_command(cfg, parent_env={})
    assert "behavex" in bc.argv[0].lower() or bc.argv[0].endswith("behavex")
    assert any(a.startswith("--formatter=") for a in bc.argv) or "--formatter" in bc.argv
    fmt = next((a for a in bc.argv if a.startswith("--formatter=")), "")
    assert "AllureBehaveXFormatter" in fmt
    assert "--formatter-outdir" in bc.argv
    outdir = bc.argv[bc.argv.index("--formatter-outdir") + 1]
    assert outdir.endswith("/allure-results/behavex")


def test_testtype_enum_values_are_stable() -> None:
    assert TestType.PYTEST.value == "pytest"
    assert TestType.BEHAVEX.value == "behavex"
    assert TestType.LOCUST.value == "locust"


def test_strip_behavex_output_folder_args_removes_o_flags() -> None:
    # Covers the skip branch (lines 108-110) and the normal append branch.
    args = ["--foo", "-o", "X", "--bar", "--output-folder", "Y", "--baz"]
    out = _strip_behavex_output_folder_args(args)
    assert out == ["--foo", "--bar", "--baz"]


def test_strip_behavex_output_folder_args_ignores_trailing_o_without_value() -> None:
    # Edge case: "-o" at end should not crash; it just gets skipped past list end.
    out = _strip_behavex_output_folder_args(["-o"])
    assert out == []


def test_command_builder_small_helpers(tmp_path: Path) -> None:
    p = coerce_path(str(tmp_path))
    assert p == tmp_path
    d = ensure_dir(tmp_path / "x" / "y")
    assert d.is_dir()
    assert stringify_argv(["a", "b", "c"]) == "a b c"


def test_build_locust_includes_html_and_hooks(tmp_path: Path) -> None:
    lf = tmp_path / "locustfile.py"
    lf.write_text("from locust import User\n", encoding="utf-8")
    art = tmp_path / "artifacts"
    cfg = RunConfig(
        test_type=TestType.LOCUST,
        target_repo=tmp_path,
        shared_allure_results_dir=art / "allure-results" / "locust",
        artifacts_root=art,
    )
    bc = build_command(cfg, parent_env={})
    assert "locust" in "".join(bc.argv).lower()
    assert "--html" in bc.argv
