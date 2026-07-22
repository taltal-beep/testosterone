"""Smoke tests for ``testo_core.sandbox_api`` (no long-lived processes)."""

from __future__ import annotations

from testo_core import sandbox_api as sa


def test_sample_target_repo_exists() -> None:
    p = sa.sample_target_repo()
    assert p.is_dir()
    assert (p / "mock_api.py").exists() or list(p.iterdir())


def test_mock_base_url_format() -> None:
    assert str(sa.MOCK_BASE_URL).startswith("http")


def test_is_managed_process_alive_false_by_default() -> None:
    assert sa.is_managed_process_alive() is False
