---
type: spec
status: current
created: 2026-10-30
updated: 2026-10-30
related: "Shared Resource Pools, Resource Pools and Leases, Resource Lifecycle Hooks"
---

# Human-Run Resource Provider - 2026-10-30

[Index](../Index.md) · [Shared Resource Pools](../Processes%20&%20Guides/Shared%20Resource%20Pools.md) · [Resource Lifecycle Hooks - 2026-10-26](Resource%20Lifecycle%20Hooks%20-%202026-10-26.md)

## Context

[Resource Lifecycle Hooks](Resource%20Lifecycle%20Hooks%20-%202026-10-26.md) left a "provider" (`create`, `reset`, `check`, `destroy`, `list`) and dynamic pools as options. The owner's rule for them: **Testosterone must never create or delete VMs on its own.** Pools stay fixed lists of keys in `testosterone.yaml`; the only automatic commands are the user's own hooks, which reset or check a key that already exists.

What a provider still adds under that rule: seeing whether a pool matches the real VMs (keys that vanished, leftovers outside the pool), and later a safe, logged way for a person to add or remove VMs.

## Decision

A pool's `provider:` holds the user's own shell commands. Testosterone ships no VMware, cloud or hypervisor code and holds no credentials. Provider commands run only from `testo pool`, typed by a person, on that person's machine.

1. **Read-only first (this change).** `provider.list` prints the keys that exist. `testo pool status [POOL] [--check]` compares that with the pool, shows each key's lease state, and with `--check` runs the pool's existing `on_check` on free keys (a held key is never checked). It changes nothing: no disable, no lease, no command besides `list` and `on_check`. Exit `1` when a pool needs a look, so a CI schedule can warn.
2. **Never automatic, enforced.** `ResourcePool.to_json` never includes `provider`, so it never reaches a team server or a stage's workers. `tests/unit/testo_core/test_pool_provider.py` fails if any module besides `testo_core/cli/commands/pool.py` imports `testo_core.resources.provider`.
3. **`on_check` is reused**, not a second `provider.check`: one "is this key usable?" command, whether run on take or by `testo pool status --check`.

Next, in its own pull request: `testo pool add / remove / sweep` for the user's `create` and `destroy` commands. A dry run unless `--apply`, refused unless the verb is listed under `provider.allow`, capped by `max_items` and a few keys per command, `destroy` limited to names with `name_prefix` that nobody holds and that aren't listed in `items`, and every call logged with who ran it.

## Options considered

- **Stop at fixed pools** (no provider). Safe, but drift and leftovers stay invisible until a test fails on a missing VM.
- **Automatic dynamic pools** (create when the pool runs dry, destroy when a lease ends). This is how Testcontainers and cloud autoscalers work. Rejected: it breaks the owner's rule even if off by default, and brings quotas, cost and orphan handling.
- **A Python provider class** (`provider: module:Class`). Possible later under the same rules; shell commands cover the users today.

## Consequences

- Nothing changes for a pool without `provider:`. `testo pool status` on such a pool shows lease states and `?` for existence.
- A failing `provider.list` is reported (exit `3`), never guessed from: existence shows `?`.
- Leftovers are only reported. Removing them is a person's job, with their own scripts now and with `testo pool sweep --apply` after the next change.
