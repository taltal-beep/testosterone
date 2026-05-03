from __future__ import annotations

import pytest

from tests.e2e.verifiers.artifact_bundle import assert_artifact_content_redacted


def test_artifact_redaction_check_accepts_clean_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UQO_E2E_GITHUB_TOKEN", "secret-gh")
    assert_artifact_content_redacted("safe log content")


def test_artifact_redaction_check_rejects_token_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UQO_E2E_GITLAB_TOKEN", "secret-gl")
    with pytest.raises(AssertionError):
        assert_artifact_content_redacted("leaked token: secret-gl")

