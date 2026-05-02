from __future__ import annotations

import time
from pathlib import Path

import pytest

from uqo_core.cli import NDJSON_EVENT_TYPES, SUMMARY_SCHEMA_KEYS, _event_to_ndjson
from uqo_core.command_builders import BuiltCommand
from uqo_core.runners import LogEvent, RunResult


@pytest.mark.contract
def test_summary_schema_keys_are_stable() -> None:
    assert SUMMARY_SCHEMA_KEYS == (
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


@pytest.mark.contract
def test_ndjson_event_type_set_is_stable() -> None:
    assert NDJSON_EVENT_TYPES == frozenset({"log", "run_result", "unknown"})


@pytest.mark.contract
def test_ndjson_log_event_shape() -> None:
    payload = _event_to_ndjson(LogEvent(ts=123.0, stream="stdout", line="hello\n"))
    assert payload == {"event": "log", "stream": "stdout", "line": "hello\n", "ts": 123.0}


@pytest.mark.contract
def test_ndjson_run_result_event_shape(tmp_path: Path) -> None:
    cmd = BuiltCommand(
        argv=["pytest", "-q"],
        cwd=tmp_path,
        env={"UQO_RUN_ID": "rid-123", "UQO_LAST_TEST_TYPE": "pytest"},
    )
    rr = RunResult(
        returncode=0,
        started_at=time.time() - 1.0,
        finished_at=time.time(),
        command=cmd,
    )
    payload = _event_to_ndjson(rr)

    assert payload["event"] == "run_result"
    assert payload["returncode"] == 0
    assert payload["run_id"] == "rid-123"
    assert payload["test_type"] == "pytest"
    assert payload["cwd"] == str(tmp_path)
