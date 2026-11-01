"""Quarantined tests set from the UI, API or CLI (``quarantined_test``).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quarantined_test",
        sa.Column("id", AutoString(length=64), nullable=False),
        sa.Column("cycle", AutoString(length=512), nullable=False),
        sa.Column("test", AutoString(length=1024), nullable=False),
        sa.Column("reason", AutoString(length=500), nullable=False),
        sa.Column("owner", AutoString(length=200), nullable=False),
        sa.Column("added_by", AutoString(length=64), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("quarantined_test", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_quarantined_test_cycle"), ["cycle"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("quarantined_test", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_quarantined_test_cycle"))
    op.drop_table("quarantined_test")
