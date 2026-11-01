"""Schema migrations for the run history database (Alembic, run in-process).

Every table Testosterone owns is described twice: by the SQLModel classes in
:mod:`testo_core.repository.models`, which the code reads and writes through,
and by the revision scripts in ``versions/``, which are the only thing that
changes a database that already has data. ``SQLModel.metadata.create_all()`` is
no longer called on a real database: :func:`upgrade_to_head` is.

Rules:

- A model change ships with a revision in the same pull request. The test
  ``tests/unit/testo_core/repository/test_migrations.py`` compares the two and
  fails when they differ.
- Databases created by ``create_all()`` before revision ``0001`` existed (every
  install up to 1.5.0) have the tables but no ``alembic_version`` row.
  :func:`upgrade_to_head` recognises them by any of our tables, brings
  them to the baseline shape (tables and columns an older install never got,
  the way the stores used to patch themselves at startup), stamps them at the
  baseline and upgrades from there, so nothing is lost and nobody runs a
  command by hand.
- Several processes may start on one database at once (parallel CI workers
  leasing keys, ``testo run`` next to ``testo-api``). The first one upgrades;
  the others see a database error, find the schema already at head and go on.
- New revisions: ``python scripts/db_revision.py "add x to y"`` writes the
  script from the model diff; read it before committing, autogenerate misses
  renames and server defaults.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DatabaseError
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

SCRIPT_LOCATION = Path(__file__).resolve().parent
BASELINE_REVISION = "0001"
_VERSION_TABLE = "alembic_version"

# Alembic's own state is per Config, so running two upgrades at once in one
# process would only waste work; the lock keeps the first run exclusive.
_UPGRADE_LOCK = threading.Lock()


def alembic_config(connection: Connection | None = None) -> Config:
    """An Alembic config pointing at this package, with no ``alembic.ini``."""
    cfg = Config()
    cfg.set_main_option("script_location", str(SCRIPT_LOCATION))
    # Revision scripts are named by number, not by hash, so the history reads in order.
    cfg.set_main_option("file_template", "%%(rev)s_%%(slug)s")
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def head_revision() -> str:
    """The newest revision in ``versions/``."""
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError("no migration scripts found")
    return head


def current_revision(connection: Connection) -> str | None:
    """The revision the database is stamped at, or None when it has no version table."""
    return MigrationContext.configure(connection).get_current_revision()


def is_legacy_schema(connection: Connection) -> bool:
    """True for a database built before migrations existed: some of our tables, no version table.

    Any of them counts: a database first opened by ``testo lease`` has the
    resource tables and no ``runrecord``.
    """
    import testo_core.repository.models  # noqa: F401  (registers every table)

    tables = set(inspect(connection).get_table_names())
    if _VERSION_TABLE in tables:
        return False
    return any(name in tables for name in SQLModel.metadata.tables)


def _sql_default(column) -> str:  # noqa: ANN001 - sqlalchemy Column
    """A literal for ``ADD COLUMN ... NOT NULL DEFAULT`` matching the model's Python default."""
    default = column.default.arg if column.default is not None else None
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, (int, float)):
        return repr(default)
    if column.nullable:
        return "NULL"
    return "''"


def reconcile_legacy_schema(connection: Connection) -> None:
    """Give a ``create_all()``-era database every table and column of the baseline.

    Older installs lack whole tables (resource pools arrived in 1.4) or columns
    (``reportarchive`` counters, ``resource_item.clean``). ``create_all`` adds the
    missing tables; missing columns are added with the model's default, which is
    what :mod:`testo_core.resources.store` used to do for its own tables.
    """
    import testo_core.repository.models  # noqa: F401  (registers every table)

    SQLModel.metadata.create_all(connection)
    inspector = inspect(connection)
    for table in SQLModel.metadata.sorted_tables:
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in have:
                continue
            kind = column.type.compile(dialect=connection.dialect)
            null = "NULL" if column.nullable else "NOT NULL"
            default = _sql_default(column)
            connection.execute(
                text(
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} {kind} {null} "
                    f"DEFAULT {default}"
                )
            )
            logger.info("added %s.%s to a pre-migration database", table.name, column.name)


def _upgrade(connection: Connection) -> str:
    if is_legacy_schema(connection):
        logger.info(
            "run history database predates migrations; stamping it at %s", BASELINE_REVISION
        )
        reconcile_legacy_schema(connection)
        command.stamp(alembic_config(connection), BASELINE_REVISION)
    before = current_revision(connection)
    head = head_revision()
    if before != head:
        command.upgrade(alembic_config(connection), "head")
        logger.info("run history database upgraded from %s to %s", before or "empty", head)
    return head


def upgrade_to_head(engine: Engine, *, wait_s: float = 30.0) -> str:
    """Bring ``engine``'s database to the newest revision and return it.

    Idempotent: a database already at head is left alone after one query. When
    another process is upgrading the same database (parallel CI workers taking
    leases), this one's attempt fails on the lock or the half-built table; it
    then waits up to ``wait_s`` for the other to finish and goes on.
    """
    deadline = time.monotonic() + wait_s
    with _UPGRADE_LOCK:
        while True:
            try:
                with engine.begin() as connection:
                    return _upgrade(connection)
            except DatabaseError as exc:
                with engine.connect() as connection:
                    if _at_head(connection):
                        return head_revision()
                if time.monotonic() >= deadline:
                    raise
                logger.debug("schema upgrade lost a race (%s); waiting for the winner", exc)
                time.sleep(0.2)


def _at_head(connection: Connection) -> bool:
    try:
        return current_revision(connection) == head_revision()
    except DatabaseError:  # the other process holds the lock; try again shortly
        return False
