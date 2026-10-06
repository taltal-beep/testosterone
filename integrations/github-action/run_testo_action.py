"""GitHub Actions wrapper around ``testo run --ci``.

Runs one cycle, echoes the NDJSON event stream, and turns the final
``plan_finished`` event into step outputs (``exit_code``, ``status``,
``summary_json``, ``summary_path``).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _parse_bool(value: str, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def build_command(*, config_path: str, cycle: str, ci_mode: bool, persist: bool) -> list[str]:
    cmd = ["testo", "run"]
    if config_path:
        cmd += ["--config", config_path]
    if cycle:
        cmd += ["--cycle", cycle]
    if ci_mode:
        cmd.append("--ci")
    if not persist:
        cmd.append("--no-persist")
    return cmd


def _extract_summary(stdout: str, *, fallback_exit_code: int) -> dict[str, Any]:
    """Return the last NDJSON object carrying an ``exit_code`` (``plan_finished`` or ``error``)."""
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "exit_code" in payload:
            return payload
    return {
        "event": "error",
        "error": "Unable to parse a plan_finished event from testo output.",
        "exit_code": int(fallback_exit_code),
    }


def _status_from_exit_code(exit_code: int) -> str:
    if exit_code == 0:
        return "success"
    if exit_code == 1:
        return "failure"
    if exit_code == 2:
        return "invalid_input"
    if exit_code == 3:
        return "infra_failure"
    return "internal_error"


def _write_github_outputs(path: Path, *, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Testosterone cycle in GitHub Actions.")
    parser.add_argument("--config-path", default="")
    parser.add_argument("--cycle", default="")
    parser.add_argument("--ci-mode", default="true")
    parser.add_argument("--persist", default="true")
    parser.add_argument("--summary-path", default="")
    args = parser.parse_args(argv)

    cmd = build_command(
        config_path=str(args.config_path or "").strip(),
        cycle=str(args.cycle or "").strip(),
        ci_mode=_parse_bool(args.ci_mode, default=True),
        persist=_parse_bool(args.persist, default=True),
    )

    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=os.environ.copy())  # noqa: S603
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    summary = _extract_summary(proc.stdout or "", fallback_exit_code=int(proc.returncode))
    summary_json = json.dumps(summary, separators=(",", ":"), ensure_ascii=True)

    summary_path_arg = str(args.summary_path or "").strip()
    if not summary_path_arg:
        runner_temp = os.getenv("RUNNER_TEMP", ".")
        summary_path = Path(runner_temp) / "testo-summary.json"
    else:
        summary_path = Path(summary_path_arg)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_json + "\n", encoding="utf-8")

    outputs = {
        "exit_code": str(proc.returncode),
        "summary_json": summary_json,
        "summary_path": str(summary_path),
        "status": _status_from_exit_code(int(proc.returncode)),
    }
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        _write_github_outputs(Path(github_output), values=outputs)

    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
