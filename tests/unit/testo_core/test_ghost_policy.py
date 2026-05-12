from __future__ import annotations

from testo_core.services.ghost_policy import resolve_ghost_mode


def test_resolve_ghost_mode_defaults_to_local() -> None:
    out = resolve_ghost_mode(ghost_flag=False, no_ghost_flag=False, ci_flag=False, env={})
    assert out.enabled is False
    assert out.reason == "default_local"


def test_resolve_ghost_mode_env_auto_detect() -> None:
    out = resolve_ghost_mode(ghost_flag=False, no_ghost_flag=False, ci_flag=False, env={"GITHUB_ACTIONS": "true"})
    assert out.enabled is True
    assert out.reason == "env_detected"


def test_resolve_ghost_mode_ci_flag_enables_ghost() -> None:
    out = resolve_ghost_mode(ghost_flag=False, no_ghost_flag=False, ci_flag=True, env={})
    assert out.enabled is True
    assert out.reason == "flag_ci"


def test_resolve_ghost_mode_force_on_beats_env() -> None:
    out = resolve_ghost_mode(ghost_flag=True, no_ghost_flag=False, ci_flag=False, env={})
    assert out.enabled is True
    assert out.reason == "flag_ghost"


def test_resolve_ghost_mode_force_off_beats_everything() -> None:
    out = resolve_ghost_mode(ghost_flag=True, no_ghost_flag=True, ci_flag=True, env={"GITHUB_ACTIONS": "true"})
    assert out.enabled is False
    assert out.reason == "flag_no_ghost"
