"""Optional stochastic failures for the sandbox ``sample_target_repo``.

Used by pytest (``tests/conftest.py``) and Behave (``features/environment.py``).
When ``TESTO_SAMPLE_RANDOM_FAIL_P`` is unset or ``0``, behavior is unchanged.

Set to a probability in ``(0, 1]`` — each pytest *test* and each Behave
*scenario* rolls independently before running, so successive cycles differ.

Example::

    export TESTO_SAMPLE_RANDOM_FAIL_P=0.08
    testo run --cycle sample-all-frameworks
"""

from __future__ import annotations

import os
import random


def probability() -> float:
    raw = os.environ.get("TESTO_SAMPLE_RANDOM_FAIL_P", "").strip()
    if not raw:
        return 0.0
    try:
        p = float(raw)
    except ValueError:
        return 0.0
    return max(0.0, min(1.0, p))


def roll_fail(label: str) -> None:
    """Raise ``AssertionError`` with probability :func:`probability`."""

    p = probability()
    if p <= 0.0:
        return
    if random.random() < p:
        msg = (
            f"Random failure injection (TESTO_SAMPLE_RANDOM_FAIL_P={p:g}): {label}"
        )
        raise AssertionError(msg)
