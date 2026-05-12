"""Behave environment for mock API flow tests."""

from __future__ import annotations

import mock_api
from random_fail import roll_fail


def before_scenario(context, scenario):  # noqa: ARG001
    """Isolate scenarios that mutate in-memory item storage."""
    mock_api.ITEMS.clear()
    mock_api.NEXT_ID = 1
    roll_fail(f"behave:{scenario.name}")
