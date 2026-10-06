"""Run history: the read side of the run database.

The engine writes one :class:`~testo_core.repository.models.RunRecord` per cycle
execution (:mod:`testo_core.persistence.db_backend`). Everything that reads those
records back goes through this package, and this package only talks to storage
through :func:`testo_core.db.get_repository`:

- :mod:`.views` — flat, typed views of a record (``CompletedRunView``, ``RunSessionView``).
- :mod:`.read_model` — queries the API and services use (list, get, compare, sessions).
- :mod:`.report_links` — which HTML reports exist for a run, and their URLs.
- :mod:`.snapshots` — raw artifact files of a run, for download and diffing.
- :mod:`.s3_snapshots` — the same two lookups for pre-v1.1 runs stored in MinIO.
- :mod:`.maintenance` — metadata patches and orphaned-run cleanup.

Submodules are imported directly (``from testo_core.history.read_model import get_run``);
on-disk locations (``STATIC_HISTORY_ROOT``) live in :mod:`testo_core.paths`.
"""
