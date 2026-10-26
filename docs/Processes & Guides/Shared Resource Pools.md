---
type: guide
status: current
created: 2026-10-26
updated: 2026-10-26
---

# Shared Resource Pools

[Index](../Index.md) · [Command Reference § testo lease](../CLI%20Commands/Command%20Reference.md#testo-lease) · [Resource Pools and Leases - 2026-10-26](../Specs%20&%20ADRs/Resource%20Pools%20and%20Leases%20-%202026-10-26.md)

Parallel test workers often need something that only one of them may use at a time: a VM, a phone, a test account, a license seat, a port. A resource pool is a list of those things, by name. Testosterone gives each worker its own key from the pool and makes sure no other worker, on this machine or on another developer's laptop, gets the same key until it is given back.

Testosterone never does anything to the keys themselves. Reverting a VM, logging in to an account or rebooting a phone stays with your own tools; you can call them from optional hooks.

## Define a pool

In `testosterone.yaml` (a file with only `resources:` and no `cycles:` works too):

```yaml
resources:
  flow-vms:
    items:
      - vm-01
      - vm-02
      - { id: vm-03, labels: [win11], data: { address: 10.0.0.13 } }
    lease_ttl: 120                                   # seconds without a heartbeat before a key is free again
    max_per_user: 4                                  # optional: most keys one person may hold
    on_take: "vmrun revertToSnapshot $TESTO_RESOURCE_ID clean"   # optional, your own command
    on_release: "my-cleanup $TESTO_RESOURCE_ID"      # optional
    hook_timeout: 300                                # seconds, for each hook
  license-seats:
    count: 3                                         # keys license-seats-1 ... license-seats-3
```

| Key | Default | Meaning |
|-----|---------|---------|
| `items` | | Key names (letters, digits, `. _ @ : -`), or `{id, labels, data}`. `labels` let a worker ask for a kind of key; `data` is handed to the worker as is |
| `count` | | Instead of `items`: that many keys named `<pool>-1` to `<pool>-N` |
| `lease_ttl` | `120` | Seconds a lease lives without a heartbeat. A worker that dies frees its key after this long |
| `max_per_user` | none | Most keys one user may hold at once; more requests wait |
| `on_take` | none | Shell command run, with the variables below set, right after a key is taken. If it fails, the key is taken out of the pool (disabled) and another key is tried |
| `on_release` | none | Shell command run before a key is given back. If it fails, the key is disabled |
| `hook_timeout` | `300` | Seconds each hook may take; longer counts as a failure |

## Give each worker its own key

Wrap the command a worker runs:

```bash
testo lease run flow-vms -- pytest tests/flows -k checkout
testo lease run flow-vms --label win11 --wait 10m -- ./run_flow.sh
```

`testo lease run` waits for a free key, runs the command with these variables set, keeps the lease alive while it runs, and gives the key back when it ends, whether it passed, failed or was stopped. It exits with the command's exit code.

| Variable | Example | Meaning |
|----------|---------|---------|
| `TESTO_RESOURCE_ID` | `vm-03` | The key this worker holds |
| `TESTO_RESOURCE_POOL` | `flow-vms` | Its pool |
| `TESTO_RESOURCE_LABELS` | `win11` | Its labels, comma-separated |
| `TESTO_RESOURCE_DATA` | `{"address": "10.0.0.13"}` | Its `data`, as JSON |
| `TESTO_RESOURCE_<NAME>` | `TESTO_RESOURCE_ADDRESS=10.0.0.13` | One variable per `data` value |
| `TESTO_LEASE_ID` | `5f0c…` | Unique per lease: a safe name for this worker's own folder or log |

Scripts that can't wrap a command use `take`, `heartbeat` and `release`; see [Command Reference § testo lease](../CLI%20Commands/Command%20Reference.md#testo-lease). Run several `testo lease run` at once (one per worker, from a shell loop, a CI matrix or your own runner) and each gets a different key; when there are more workers than keys, the extra ones wait in line.

## Use a pool in a cycle

A stage can ask for keys itself with `resources:`, so `testo run` hands them out:

```yaml
cycles:
  flows:
    stages:
      - name: flow-tests
        equipment: pytest
        args: "tests/flows"
        workers: auto                 # as many pytest-xdist workers as the pool has free keys
        resources:
          pool: flow-vms
          per: worker                 # worker (default), test, or stage
          labels: [win11]             # optional: only keys with these labels
          wait: 30m                   # how long to wait for a key (default 30m; "forever" for no limit)
      - name: deploy-check
        equipment: command
        args: "./check_all.sh"
        resources: { pool: flow-vms, per: stage }
```

`resources: flow-vms` is short for `{pool: flow-vms}`.

| `per` | Who takes a key | When it goes back |
|-------|-----------------|-------------------|
| `worker` | Each pytest(-xdist) worker, once, for all the tests it runs | When the worker ends |
| `test` | Each test (pytest only); `on_take` and `on_release` run around every test, so each test gets a freshly reset key | After the test |
| `stage` | Testosterone, before the stage starts. The stage's process gets the variables above | When the stage ends. With no key within `wait`, the stage fails like a timeout (`testo run` exits `3`) |

With `per: worker` or `per: test`, the stage passes the pool down in `TESTO_RESOURCE_SPEC` and the pytest plugin in each worker takes the key, so the pytest-xdist controller holds none. Other runners can take one per worker with `testo lease run "$TESTO_RESOURCE_POOL" -- ...`. `workers: auto` needs `per: worker` or `per: test`, and counts free keys once, when the stage starts; a worker that finds none free waits in line.

The same works in plain pytest, without a cycle:

```bash
pytest -n 4 --testo-resource flow-vms                         # a key per worker
pytest --testo-resource flow-vms --testo-resource-per test --testo-resource-label win11
```

and a test reads its key from the `testo_resource` fixture (or from the variables):

```python
def test_checkout(testo_resource):
    vm = testo_resource.id  # "vm-03"
    address = testo_resource.data["address"]  # from the key's data
```

## Many developers, many laptops

Leases are kept in a database, never in files:

- **One machine:** without a server they go into this machine's run-history database (`DATABASE_URL`, `database.url`, or `./testo_history.db`). All workers on the machine share one pool.
- **A team:** set `TESTO_SERVER_URL` to the [team server](Team%20Server.md) and `TESTO_API_TOKEN` to its token, on every laptop and CI agent. Every `testo lease` then takes keys through the server, so two developers can never get the same key. If the server can't be reached, `testo lease` fails (exit `3`); it never guesses a key.

Each lease records who holds it: the user name and host of the machine, the process, and with accounts on the server, the signed-in account. Every run keeps its own artifacts folder, and `TESTO_LEASE_ID` names a per-worker folder, so developers' files don't clash either.

## See and fix the pool

The **Resources** page in the UI (under Tools) shows every pool, each key's holder, when it was taken and its last heartbeat, and how many requests wait. It refreshes every few seconds. From there, or with `testo lease`, you can:

- **Disable** a broken key so nobody gets it (`testo lease disable flow-vms vm-02 --reason "snapshot broken"`), and put it back (`testo lease enable`). Keys whose hooks failed show up here, disabled, with the reason.
- **Take a key back** from its holder (`testo lease free`; an admin on a server with accounts). The holder's next heartbeat finds it gone, and `testo lease run` warns that the lease was lost.

## How it works

- **A lease, not a lock.** A lease is a database row with an owner and an expiry time, one row per key. Taking a key is one insert, so two workers can't get the same key on any database, from any number of machines.
- **Heartbeats.** The holder pushes the expiry forward every `lease_ttl / 3` seconds. A process that crashes, is killed, or whose laptop goes to sleep stops sending them, and its key is free once `lease_ttl` passes. No stale locks to delete by hand.
- **Fair queue.** A request that finds no free key waits in line, oldest first. A request only goes ahead of an older one when they want different keys (other labels), so nobody waits behind someone who can't use the free key anyway.
- **One clock.** All times come from the database's owner: the team server, or this machine.

The pools are described by whoever uses them, so the server needs no copy of your config: each request carries the pool's keys, labels and data (never its hooks, which only run on the machine that took the key). Code: `testo_core/resources/` (`pools.py`, `store.py`, `client.py`), `testo_api/routes/resources.py`, tables `resource_item`, `resource_lease`, `resource_waiter`.
