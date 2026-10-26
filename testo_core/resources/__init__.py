"""Shared resource pools for parallel test runs: keys, leases and a fair queue.

- :mod:`~testo_core.resources.pools`: the ``resources:`` config section.
- :mod:`~testo_core.resources.store`: leases in the run-history database.
- :mod:`~testo_core.resources.client`: take and hold a key, here or on a team server.
"""
