---
type: spec
status: current
created: 2026-10-26
updated: 2026-10-26
related: "Shared Resource Pools, Team Server, Scale Runs and Stages"
---

# Resource Pools and Leases - 2026-10-26

[Index](../Index.md) · [Shared Resource Pools](../Processes%20&%20Guides/Shared%20Resource%20Pools.md) · [Scale Runs and Stages - 2026-10-24](Scale%20Runs%20and%20Stages%20-%202026-10-24.md)

## Context

Testosterone could run stages in parallel (`max_parallel_stages`) and pass `workers` to the framework, but nothing stopped two parallel workers from using the same scarce thing. The case that started this: flow tests on VMware VMs, where every test worker needs its own clean, identifiable VM, and several developers run the whole suite at the same time from their own laptops. The team's answer was a lock-file system tied to the process that handed out unique keys. Lock files break in known ways: a crashed process leaves its lock behind; they only work on one machine; whoever polls at the right moment wins; nobody can see who holds what; and a broken VM keeps being handed out.

The owner asked for a general answer, not a VM feature: the system under test already has its own VM actions, so Testosterone should only make parallel runs safe.

## Decision

**Pools of opaque keys, handed out as leases from the database.**

1. **Pools in config.** A top-level `resources:` mapping names pools of keys (`items`, or `count: N`), with optional labels and data per key, `lease_ttl`, `max_per_user`, and optional `on_take` / `on_release` shell hooks (`testo_core/resources/pools.py`). Testosterone never interprets a key.
2. **A lease is a row.** `resource_lease` has the key (pool, item) as its primary key, so taking a key is one insert that fails for a second holder on SQLite, Postgres and MySQL alike, across processes and machines. The holder heartbeats every `lease_ttl / 3`; a row past `expires_at` is deleted by the next take, and a heartbeat after expiry is refused, so a holder that was presumed dead can't come back and share the key (`testo_core/resources/store.py`).
3. **A fair queue.** A request that finds nothing free becomes a row in `resource_waiter` (with the keys it would accept) and asks again every two seconds with the same id. A key goes to the oldest waiter that can use it; a younger one goes first only when the older ones want other keys. A waiter that stops asking expires after 30 seconds.
4. **Broken keys leave the pool.** `resource_item` remembers each key as clients describe it, plus a `disabled` flag. A failing hook disables its key and the worker tries another; people disable and enable keys from the CLI or the Resources page.
5. **One client, two places.** `testo_core/resources/client.py` talks to the local run-history database, or to a team server's `/api/v1/resources` when `TESTO_SERVER_URL` is set. `acquire()` waits, runs `on_take`, and returns a `HeldLease` that heartbeats in a thread and runs `on_release` and gives the key back on exit. `testo lease run POOL -- CMD` is the CLI wrapper; workers read `TESTO_RESOURCE_ID` and friends.
6. **The server learns pools from its users.** A take request carries the pool's keys, labels and data (never its hooks), so a team server needs no copy of each repository's config, and every client decides what it would accept. Reads never show lease ids; taking a key back from someone else needs `admin` with accounts.

## Options considered

- **Keep lock files, but use OS locks (`flock`).** Freed when the process dies, but still one machine, no queue, no view. Rejected for the many-laptops case.
- **Redis, etcd or Consul leases.** They have TTL leases built in, but they are another service to run and secure, and they know nothing about pools, labels or the team's runs. The database is already there on every install and on the team server.
- **Jenkins Lockable Resources / GitLab `resource_group`.** Close in spirit, but tied to one CI system and to whole jobs, not to the workers inside a job, and invisible to a developer running from a laptop.
- **Pools defined only on the server.** One source of truth, but every repository change would need a server change, and a laptop without a server (one machine, parallel workers) would need a second code path. Rejected; the server instead remembers what clients describe.
- **Reset VMs ourselves (snapshot revert).** Rejected at the owner's request: the system under test owns its actions. The hooks are the seam.

## Consequences

- Keys are safe from double use as long as every holder heartbeats; a process frozen for longer than `lease_ttl` (a debugger, a suspended VM) loses its key. Pick `lease_ttl` with that in mind; `testo lease run` warns when it lost a lease while the command ran.
- Waiting is polling (one small request every two seconds per waiter). Fine for tens of workers; a pool with hundreds of waiters would want a push channel.
- The user name in a lease comes from the client's OS account unless the server has accounts and a signed-in session; the shared API token names no one.
- Keys nobody has described for a week, and that are free and enabled, drop off the Resources page; their rows stay.
- The queue position is lost if a waiter's process restarts (it gets a new id). That's the price of not keeping state on the client.

## Next

Phase 2 ties pools into cycles: a stage's `resources:` hands each pytest-xdist worker its own key, and `workers: auto` matches the worker count to the free keys. Later: timing-based splitting of tests across keys, then per-stage CPU and memory limits in the container runner.
