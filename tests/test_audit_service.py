"""``AuditService`` delegates without running generators to completion."""

from __future__ import annotations

from pathlib import Path

from uqo_core.services.audit_service import AuditService


def test_stream_audit_is_generator(tmp_path: Path) -> None:
    gen = AuditService.stream_audit(target_repo=tmp_path, artifacts_root=tmp_path)
    assert hasattr(gen, "__iter__")
