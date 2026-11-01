"""Write a new run history migration from the difference between the models and a fresh database.

Usage::

    python scripts/db_revision.py "add cycle column to runrecord"

Builds the current head schema in a throwaway SQLite database, compares it with
``testo_core.repository.models`` and writes ``testo_core/repository/migrations/versions/<n>_<slug>.py``.
Read the script before committing it: autogenerate cannot see a rename (it
emits drop + add) and ignores server defaults. Then run
``pytest tests/unit/testo_core/repository/test_migrations.py``.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testo_core.repository import migrations  # noqa: E402


def _next_revision_id() -> str:
    versions = migrations.SCRIPT_LOCATION / "versions"
    numbers = [int(p.name[:4]) for p in versions.glob("[0-9][0-9][0-9][0-9]_*.py")]
    return f"{(max(numbers) if numbers else 0) + 1:04d}"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].strip():
        print(__doc__)
        return 2
    message = argv[1].strip()
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{Path(tmp) / 'scratch.db'}")
        migrations.upgrade_to_head(engine)
        with engine.begin() as connection:
            command.revision(
                migrations.alembic_config(connection),
                message=message,
                autogenerate=True,
                rev_id=_next_revision_id(),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
