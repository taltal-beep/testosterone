"""Wall-duration fallback for engine-sourced run records."""

from __future__ import annotations

import pytest

from testo_core.run_history import _wall_duration_ms_from_metadata


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"wall_duration_ms": 1234.0, "duration_s": 9.0}, 1234.0),
        ({"duration_s": 1.5}, 1500.0),
        ({"started_at": 10.0, "finished_at": 12.25}, 2250.0),
        ({}, 0.0),
    ],
)
def test_wall_duration_ms_falls_back_to_engine_duration(metadata: dict, expected: float) -> None:
    assert _wall_duration_ms_from_metadata(metadata) == pytest.approx(expected)
