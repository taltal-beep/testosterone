from __future__ import annotations

from tests.conftest import CleanupLedger


def assert_no_cleanup_failures(ledger: CleanupLedger) -> None:
    failed = [entry for entry in ledger.records if entry.status == "cleanup_failed"]
    if failed:
        formatted = ", ".join(f"{entry.provider}:{entry.resource_id}" for entry in failed)
        raise AssertionError(f"cleanup failures detected: {formatted}")

