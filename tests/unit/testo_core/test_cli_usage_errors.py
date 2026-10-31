"""Usage errors print a short message and exit 2, never a traceback."""

from __future__ import annotations

from pathlib import Path

import pytest

from testo_core.cli.app import main
from testo_core.config.errors import PlanNotFoundError
from testo_core.config.loader import load_config
from testo_core.config.resolver import resolve_plan


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["frobnicate"], "No such command 'frobnicate'"),
        (["run", "--bogus"], "No such option: --bogus"),
        (["version", "extra-arg"], "Got unexpected extra argument"),
    ],
)
def test_usage_error_prints_message_not_traceback(
    argv: list[str], expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert expected in err
    assert "Try 'testo" in err
    assert "Traceback" not in err


def test_missing_cycle_with_several_cycles_says_to_pick_one(tmp_path: Path) -> None:
    cfg = tmp_path / "testosterone.yaml"
    cfg.write_text(
        "cycles:\n"
        "  a: {stages: [{name: s, equipment: command, args: [true]}]}\n"
        "  b: {stages: [{name: s, equipment: command, args: [true]}]}\n",
        encoding="utf-8",
    )
    config = load_config(cfg)
    with pytest.raises(PlanNotFoundError) as info:
        resolve_plan(config, plan_name=None)
    message = str(info.value)
    assert "pick one with --cycle" in message
    assert "<unspecified>" not in message
    assert "a, b" in message
