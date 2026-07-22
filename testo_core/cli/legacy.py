from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from testo_core.services import (
    SCHEMA_VERSION,
    ConfigValidationError,
    EngineExitCode,
    EngineRequest,
    HeadlessEngineService,
    load_run_specs_from_yaml,
    resolve_ghost_mode,
)
from testo_core.services.ci_provenance import detect_ci_provenance
from testo_core.services.headless_engine import HeadlessEngineError


def _cli_pkg() -> Any:
    """Return :mod:`testo_core.cli` so monkeypatches on the parent package
    propagate into the legacy ``_run_command`` body.

    Resolved lazily inside the helpers below; importing the parent at module
    load time would create a cycle.
    """
    from testo_core import cli as _cli

    return _cli

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
    ghost_group = run_parser.add_mutually_exclusive_group()
    ghost_group.add_argument("--ghost", action="store_true", help="Force ghost mode (non-interactive CI behavior)")
    ghost_group.add_argument("--no-ghost", action="store_true", help="Disable ghost mode even when CI env is detected")
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
        command = event_payload.command
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
    _cli = _cli_pkg()
    _load = getattr(_cli, "load_run_specs_from_yaml", load_run_specs_from_yaml)
    _detect_ci = getattr(_cli, "detect_ci_provenance", detect_ci_provenance)
    _engine_cls = getattr(_cli, "HeadlessEngineService", HeadlessEngineService)
    _os = getattr(_cli, "os", os)
    try:
        specs = _load(Path(args.config))
    except ConfigValidationError as exc:
        _write_json_stdout(
            {
                "schema_version": SCHEMA_VERSION,
                "error": str(exc),
                "exit_code": int(EngineExitCode.INVALID_INPUT),
            }
        )
        return int(EngineExitCode.INVALID_INPUT)

    ghost = resolve_ghost_mode(
        ghost_flag=bool(args.ghost),
        no_ghost_flag=bool(args.no_ghost),
        ci_flag=bool(args.ci),
        env=_os.environ,
    )
    ghost_enabled = bool(ghost.enabled)
    provenance = _detect_ci(_os.environ) if ghost_enabled else None

    request = EngineRequest(
        runs=specs,
        trigger_source="ci" if ghost_enabled else "cli",
        ci_mode=ghost_enabled,
        persist=not bool(args.no_persist),
        provenance=provenance,
    )
    engine = _engine_cls()
    stream_json = bool(args.stream_json)
    print_summary = True

    try:
        gen = engine.stream(request)
        while True:
            try:
                event = next(gen)
                if stream_json:
                    _write_json_stdout(_event_to_ndjson(event.payload))
                elif not ghost_enabled and getattr(event.payload, "line", None):
                    sys.stderr.write(str(event.payload.line))
            except StopIteration as stop:
                summary = stop.value
                if print_summary:
                    payload = summary.to_dict()
                    missing_keys = [k for k in SUMMARY_SCHEMA_KEYS if k not in payload]
                    if missing_keys:
                        raise RuntimeError(
                            f"Engine summary missing required key(s): {', '.join(missing_keys)}"
                        ) from stop
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
    except HeadlessEngineError as exc:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "error": str(exc),
            "exit_code": int(exc.exit_code),
        }
        if getattr(exc, "details", None):
            payload["details"] = exc.details
        _write_json_stdout(payload)
        return int(exc.exit_code)
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
