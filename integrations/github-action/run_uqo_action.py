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


def _parse_ghost_mode(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"auto", "true", "false"}:
        return normalized
    return "auto"


def _parse_runner_prebuilt(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"auto", "true", "false"}:
        return normalized
    return "auto"


def build_command(*, config_path: str, ci_mode: bool, stream_json: bool, persist: bool, ghost_mode: str) -> list[str]:
    cmd = ["uqo", "run", "--config", config_path]
    if ci_mode:
        cmd.append("--ci")
    if ghost_mode == "true":
        cmd.append("--ghost")
    elif ghost_mode == "false":
        cmd.append("--no-ghost")
    if stream_json:
        cmd.append("--stream-json")
    if not persist:
        cmd.append("--no-persist")
    return cmd


def _extract_summary(stdout: str, *, fallback_exit_code: int) -> dict[str, Any]:
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
        "schema_version": "1",
        "error": "Unable to parse summary JSON from uqo output.",
        "exit_code": int(fallback_exit_code),
        "runs": [],
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
    parser = argparse.ArgumentParser(description="Run UQO in GitHub Actions.")
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--ci-mode", default="true")
    parser.add_argument("--stream-json", default="false")
    parser.add_argument("--persist", default="true")
    parser.add_argument("--ghost-mode", default="auto")
    parser.add_argument("--runner-image", default="")
    parser.add_argument("--runner-prebuilt", default="auto")
    parser.add_argument("--summary-path", default="")
    args = parser.parse_args(argv)

    ci_mode = _parse_bool(args.ci_mode, default=True)
    stream_json = _parse_bool(args.stream_json, default=False)
    persist = _parse_bool(args.persist, default=True)
    ghost_mode = _parse_ghost_mode(args.ghost_mode)
    runner_prebuilt = _parse_runner_prebuilt(args.runner_prebuilt)
    cmd = build_command(
        config_path=args.config_path,
        ci_mode=ci_mode,
        stream_json=stream_json,
        persist=persist,
        ghost_mode=ghost_mode,
    )

    env = os.environ.copy()
    runner_image = str(args.runner_image or "").strip()
    if runner_image:
        env["UQO_RUNNER_IMAGE"] = runner_image
    if runner_prebuilt != "auto":
        env["UQO_RUNNER_PREBUILT"] = runner_prebuilt

    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)  # noqa: S603
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    summary = _extract_summary(proc.stdout or "", fallback_exit_code=int(proc.returncode))
    summary_json = json.dumps(summary, separators=(",", ":"), ensure_ascii=True)
    run_id = ""
    runs = summary.get("runs")
    if isinstance(runs, list) and runs:
        first = runs[0] if isinstance(runs[0], dict) else {}
        run_id = str(first.get("run_id") or "")

    summary_path_arg = str(args.summary_path or "").strip()
    if not summary_path_arg:
        runner_temp = os.getenv("RUNNER_TEMP", ".")
        summary_path = Path(runner_temp) / "uqo-summary.json"
    else:
        summary_path = Path(summary_path_arg)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_json + "\n", encoding="utf-8")

    outputs = {
        "exit_code": str(proc.returncode),
        "run_id": run_id,
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
