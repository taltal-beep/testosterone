"""Engine exit-code taxonomy (kept compatible with the legacy headless engine).

The CLI must propagate these unchanged so existing CI consumers continue to
react to specific codes.

The mapping is intentionally identical to
:class:`testo_core.services.headless_engine.EngineExitCode` so a future
internal cleanup can simply re-export this class.
"""

from __future__ import annotations

from enum import IntEnum


class EngineExitCode(IntEnum):
    """High-level outcome categorisation for the ``testo`` process."""

    SUCCESS = 0
    DOMAIN_FAILURE = 1
    INVALID_INPUT = 2
    INFRA_FAILURE = 3
    INTERNAL_ERROR = 4


def classify_exit_code(
    returncodes: list[int],
    *,
    infra_error: Exception | None,
) -> EngineExitCode:
    """Bucket a list of stage returncodes into an :class:`EngineExitCode`.

    Mirrors :func:`testo_core.services.headless_engine._classify_exit_code`
    so contract tests keep passing while the engine internals are migrated.
    """
    if infra_error is not None:
        return EngineExitCode.INFRA_FAILURE
    if not returncodes:
        return EngineExitCode.INTERNAL_ERROR
    if any(int(rc) in (124, 127) for rc in returncodes):
        return EngineExitCode.INFRA_FAILURE
    if any(int(rc) != 0 for rc in returncodes):
        return EngineExitCode.DOMAIN_FAILURE
    return EngineExitCode.SUCCESS
