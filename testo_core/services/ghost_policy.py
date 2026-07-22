from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from testo_core.services.ci_provenance import detect_ci_environment


@dataclass(frozen=True)
class GhostModeResolution:
    enabled: bool
    reason: str


def resolve_ghost_mode(
    *,
    ghost_flag: bool,
    no_ghost_flag: bool,
    ci_flag: bool,
    env: Mapping[str, str] | None = None,
) -> GhostModeResolution:
    if no_ghost_flag:
        return GhostModeResolution(enabled=False, reason="flag_no_ghost")
    if ghost_flag:
        return GhostModeResolution(enabled=True, reason="flag_ghost")
    if ci_flag:
        return GhostModeResolution(enabled=True, reason="flag_ci")
    if detect_ci_environment(env):
        return GhostModeResolution(enabled=True, reason="env_detected")
    return GhostModeResolution(enabled=False, reason="default_local")
