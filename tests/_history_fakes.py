"""Stand-ins for the run history read model, for service tests that build their own run lists."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


def cycle_runs_from(runs: Sequence[Any]) -> Callable[..., list[Any]]:
    """A fake ``list_cycle_runs`` over ``runs`` (newest first): same filters as the real one."""

    def list_cycle_runs(cycle: str, *, limit: int = 500, before_run_id: str | None = None):
        picked = [r for r in runs if r.cycle == cycle]
        if before_run_id is not None:
            index = next((i for i, r in enumerate(picked) if r.run_id == before_run_id), None)
            picked = [] if index is None else picked[index + 1 :]
        return picked[: max(0, int(limit))]

    return list_cycle_runs
