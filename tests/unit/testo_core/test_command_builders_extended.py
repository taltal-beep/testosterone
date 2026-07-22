"""Extended coverage for ``testo_core.command_builders``."""

from __future__ import annotations

from pathlib import Path

from testo_core.command_builders import (
    RunConfig,
    TestType,
    _strip_behavex_output_folder_args,
    build_command,
    coerce_path,
    ensure_dir,
    stringify_argv,
)


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
    assert TestType.BEHAVE_NATIVE.value == "behave_native"


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
