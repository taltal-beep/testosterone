from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from uqo_core.services import (
    ConfigValidationError,
    EngineExitCode,
    EngineRequest,
    SCHEMA_VERSION,
    HeadlessEngineService,
    load_run_specs_from_yaml,
)

SUMMARY_SCHEMA_KEYS: tuple[str, ...] = (
    "schema_version",
    "trigger_source",
    "ci_mode",
    "persist",
    "exit_code",
    "aggregate_returncode",
    "started_at",
    "finished_at",
    "duration_s",
    "runs",
    "error",
)
NDJSON_EVENT_TYPES: frozenset[str] = frozenset({"log", "run_result", "unknown"})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uqo", description="Unified Quality Orchestration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute one or more runs from a YAML config")
    run_parser.add_argument("--config", required=True, help="Path to YAML config file")
    run_parser.add_argument("--ci", action="store_true", help="CI mode: strict machine-readable stdout")
    run_parser.add_argument("--json", action="store_true", help="Print final summary JSON to stdout")
    run_parser.add_argument("--stream-json", action="store_true", help="Emit NDJSON event objects to stdout")
    run_parser.add_argument("--no-persist", action="store_true", help="Run without DB/history persistence")
    return parser


def _write_json_stdout(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _event_to_ndjson(event_payload: Any) -> dict[str, Any]:
    if hasattr(event_payload, "stream") and hasattr(event_payload, "line"):
        return {
            "event": "log",
            "stream": str(event_payload.stream),
            "line": str(event_payload.line),
            "ts": float(event_payload.ts),
        }
    if hasattr(event_payload, "returncode") and hasattr(event_payload, "command"):
        command = getattr(event_payload, "command")
        env = getattr(command, "env", {})
        run_id = env.get("UQO_AUDIT_RUN_ID") or env.get("UQO_RUN_ID")
        return {
            "event": "run_result",
            "returncode": int(event_payload.returncode),
            "started_at": float(event_payload.started_at),
            "finished_at": float(event_payload.finished_at),
            "run_id": run_id,
            "test_type": str(env.get("UQO_LAST_TEST_TYPE", "unknown")),
            "cwd": str(command.cwd),
        }
    return {"event": "unknown", "value": str(event_payload)}


def _run_command(args: argparse.Namespace) -> int:
    try:
        specs = load_run_specs_from_yaml(Path(args.config))
    except ConfigValidationError as exc:
        _write_json_stdout(
            {
                "schema_version": SCHEMA_VERSION,
                "error": str(exc),
                "exit_code": int(EngineExitCode.INVALID_INPUT),
            }
        )
        return int(EngineExitCode.INVALID_INPUT)

    request = EngineRequest(
        runs=specs,
        trigger_source="cli",
        ci_mode=bool(args.ci),
        persist=not bool(args.no_persist),
    )
    engine = HeadlessEngineService()
    stream_json = bool(args.stream_json)
    print_summary = True

    try:
        gen = engine.stream(request)
        while True:
            try:
                event = next(gen)
                if stream_json:
                    _write_json_stdout(_event_to_ndjson(event.payload))
                elif not args.ci and getattr(event.payload, "line", None):
                    sys.stderr.write(str(event.payload.line))
            except StopIteration as stop:
                summary = stop.value
                if print_summary:
                    payload = summary.to_dict()
                    missing_keys = [k for k in SUMMARY_SCHEMA_KEYS if k not in payload]
                    if missing_keys:
                        raise RuntimeError(f"Engine summary missing required key(s): {', '.join(missing_keys)}")
                    _write_json_stdout(payload)
                return int(summary.exit_code)
    except ConfigValidationError as exc:
        _write_json_stdout(
            {
                "schema_version": SCHEMA_VERSION,
                "error": str(exc),
                "exit_code": int(EngineExitCode.INVALID_INPUT),
            }
        )
        return int(EngineExitCode.INVALID_INPUT)
    except Exception as exc:  # pragma: no cover - defensive fallback
        _write_json_stdout(
            {
                "schema_version": SCHEMA_VERSION,
                "error": str(exc),
                "exit_code": int(EngineExitCode.INTERNAL_ERROR),
            }
        )
        return int(EngineExitCode.INTERNAL_ERROR)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_command(args)
    parser.print_help()
    return int(EngineExitCode.INVALID_INPUT)


if __name__ == "__main__":
    raise SystemExit(main())
