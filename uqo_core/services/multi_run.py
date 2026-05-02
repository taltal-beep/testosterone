from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from uqo_core.command_builders import RunConfig
from uqo_core.runners import LogEvent, RunResult, UQO_DONE_MARKER

@dataclass(frozen=True)
class MultiRunState:
    running: bool
    run_completed: bool
    multi_run_active: bool
    multi_runs_remaining: int


def advance_after_run_result(*, multi_run_active: bool, multi_runs_remaining: int) -> MultiRunState:
    """Update UI completion state after one run in a possible multi-run batch finishes."""
    if not multi_run_active:
        return MultiRunState(
            running=False,
            run_completed=True,
            multi_run_active=False,
            multi_runs_remaining=0,
        )

    remaining = max(0, int(multi_runs_remaining or 0) - 1)
    finished_batch = remaining <= 0
    return MultiRunState(
        running=not finished_batch,
        run_completed=finished_batch,
        multi_run_active=not finished_batch,
        multi_runs_remaining=remaining,
    )


def aggregate_returncode(returncodes: list[int]) -> int:
    """Return a batch status code: success only when every config produced zero."""
    return 0 if returncodes and all(int(rc) == 0 for rc in returncodes) else 1


def stream_multi_run(
    configs: list[RunConfig],
    *,
    artifacts_root: Path,
    db_run_ids: list[str | None],
    run_streaming_fn: Callable[..., Iterable[LogEvent]],
    update_run_status_fn: Callable[..., None],
    failed_status: Any = "FAILED",
) -> Iterable[LogEvent | RunResult]:
    """
    Run multiple configurations as one UI batch.

    Per-config ``[UQO_DONE]`` markers are suppressed so the UI keeps polling until
    the final aggregate marker is emitted after every config has finished.
    """
    returncodes: list[int] = []
    for idx, cfg in enumerate(configs):
        db_id = db_run_ids[idx] if idx < len(db_run_ids) else None
        yield LogEvent(
            ts=time.time(),
            stream="meta",
            line=f"\n=== Run {idx + 1}/{len(configs)}: {cfg.test_type.value} in {cfg.target_repo} ===\n",
        )
        try:
            gen = iter(
                run_streaming_fn(
                    cfg,
                    artifacts_root=artifacts_root,
                    emit_done_marker=False,
                )
            )
            while True:
                try:
                    yield next(gen)
                except StopIteration as e:
                    if e.value is not None:
                        returncodes.append(int(e.value.returncode))
                        yield e.value
                    break
        except Exception as exc:
            import traceback

            if db_id:
                try:
                    update_run_status_fn(
                        db_id,
                        status=failed_status,
                        metadata={"error": str(exc), "traceback": traceback.format_exc()},
                    )
                except Exception:
                    pass
            yield LogEvent(
                ts=time.time(),
                stream="meta",
                line=f"[run {idx + 1} error] {exc}\n{traceback.format_exc()}\n",
            )
            returncodes.append(1)

    yield LogEvent(
        ts=time.time(),
        stream="meta",
        line=f"{UQO_DONE_MARKER} returncode={aggregate_returncode(returncodes)}\n",
    )
