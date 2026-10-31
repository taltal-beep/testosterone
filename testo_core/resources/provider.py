"""A pool's ``provider:``: compare the keys in a pool with the ones that really exist.

Testosterone never creates or deletes a key on its own. A provider is the
config author's own commands; this module only runs the read-only ones, and only
:mod:`testo_core.cli.commands.pool` calls it, when a person types ``testo pool``.
Leases, runs, stages and the team server never import it (a contract test checks).

``list`` prints the keys that exist, one per line (blank lines and ``#`` comments
are skipped). ``testo pool status --check`` also runs the pool's ``on_check`` on
each free key. The result says which keys are missing, which exist outside the
pool (leftovers), and which fail their check.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from testo_core.resources.client import run_command
from testo_core.resources.pools import ResourceItem, ResourcePool
from testo_core.resources.store import ItemStatus


@dataclass(frozen=True)
class Listing:
    """What ``provider.list`` printed: the keys, or why it could not run."""

    keys: tuple[str, ...] = ()
    problem: str | None = None


@dataclass(frozen=True)
class KeyReport:
    key: str
    # True/False when provider.list ran; None when the pool has no list command.
    exists: bool | None
    state: str  # free | held | disabled
    # None: not checked; "" passed; otherwise why on_check failed or was skipped.
    check: str | None = None
    check_skipped: bool = False


@dataclass(frozen=True)
class PoolReport:
    pool: str
    keys: tuple[KeyReport, ...]
    # Keys provider.list printed that the pool doesn't have: leftovers, or new ones to add.
    extra: tuple[str, ...] = ()
    list_problem: str | None = None
    has_list: bool = False
    missing: tuple[str, ...] = field(init=False)
    failed_checks: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing", tuple(k.key for k in self.keys if k.exists is False))
        object.__setattr__(
            self,
            "failed_checks",
            tuple(k.key for k in self.keys if k.check and not k.check_skipped),
        )

    @property
    def healthy(self) -> bool:
        return not (self.list_problem or self.missing or self.extra or self.failed_checks)


def item_env(pool: ResourcePool, item: ResourceItem) -> dict[str, str]:
    """``TESTO_RESOURCE_*`` for a key nobody holds (no ``TESTO_LEASE_ID``)."""
    env = {
        "TESTO_RESOURCE_ID": item.id,
        "TESTO_RESOURCE_POOL": pool.name,
        "TESTO_RESOURCE_LABELS": ",".join(item.labels),
        "TESTO_RESOURCE_DATA": json.dumps(dict(item.data), sort_keys=True),
    }
    for key, value in item.data:
        name = "".join(c if c.isalnum() else "_" for c in key.upper())
        env.setdefault(f"TESTO_RESOURCE_{name}", value)
    return env


def list_keys(pool: ResourcePool) -> Listing:
    """Run ``provider.list``; an empty listing when the pool has none."""
    command = pool.provider.list if pool.provider else None
    if not command:
        return Listing()
    problem, out = run_command(
        command, {"TESTO_RESOURCE_POOL": pool.name}, timeout_s=pool.hook_timeout_s
    )
    if problem:
        return Listing(problem=f"provider.list failed: {problem}")
    keys = (line.strip() for line in out.splitlines())
    return Listing(keys=tuple(dict.fromkeys(k for k in keys if k and not k.startswith("#"))))


def check_key(pool: ResourcePool, item: ResourceItem) -> str:
    """Run ``on_check`` on a key nobody holds: "" when it passed, else why not."""
    if not pool.on_check:
        return ""
    problem, _ = run_command(pool.on_check, item_env(pool, item), timeout_s=pool.hook_timeout_s)
    return f"on_check failed: {problem}" if problem else ""


def pool_report(
    pool: ResourcePool, items: Sequence[ItemStatus] = (), *, check: bool = False
) -> PoolReport:
    """Compare ``pool`` with what its provider lists, and optionally check each free key.

    ``items`` is the pool's lease status (who holds what); keys someone holds are
    never checked, so a check can't disturb a test that is using the key.
    """
    listing = list_keys(pool)
    has_list = bool(pool.provider and pool.provider.list)
    listed = set(listing.keys)
    status: Mapping[str, ItemStatus] = {i.item: i for i in items}
    reports: list[KeyReport] = []
    for item in pool.items:
        st = status.get(item.id)
        state = "disabled" if st and st.disabled else "held" if st and st.lease else "free"
        exists = None if not has_list or listing.problem else item.id in listed
        result: str | None = None
        skipped = False
        if check and pool.on_check:
            if state == "held":
                result, skipped = "skipped: someone holds it", True
            elif exists is False:
                result, skipped = "skipped: provider.list doesn't show it", True
            else:
                result = check_key(pool, item)
        reports.append(
            KeyReport(key=item.id, exists=exists, state=state, check=result, check_skipped=skipped)
        )
    known = {item.id for item in pool.items}
    return PoolReport(
        pool=pool.name,
        keys=tuple(reports),
        extra=tuple(k for k in listing.keys if k not in known),
        list_problem=listing.problem,
        has_list=has_list,
    )
