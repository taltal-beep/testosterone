"""Baseline: the schema every install up to 1.5.0 got from ``create_all()``.

A database created before this revision is stamped here, not rebuilt
(see :func:`testo_core.repository.migrations.upgrade_to_head`).

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlmodel.sql.sqltypes import AutoString

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("username", AutoString(length=64), nullable=False),
        sa.Column("method", AutoString(length=8), nullable=False),
        sa.Column("path", AutoString(length=1024), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_event_at"), ["at"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_event_username"), ["username"], unique=False)

    op.create_table(
        "failure_triage",
        sa.Column("id", AutoString(length=64), nullable=False),
        sa.Column("cycle", AutoString(length=512), nullable=False),
        sa.Column("signature", AutoString(length=1024), nullable=False),
        sa.Column("cause", AutoString(length=32), nullable=False),
        sa.Column("note", AutoString(length=500), nullable=False),
        sa.Column("example_message", AutoString(length=1000), nullable=False),
        sa.Column("run_id", AutoString(length=64), nullable=False),
        sa.Column("test_key", AutoString(length=200), nullable=False),
        sa.Column("marked_by", AutoString(length=64), nullable=True),
        sa.Column("marked_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("failure_triage", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_failure_triage_cycle"), ["cycle"], unique=False)

    op.create_table(
        "queued_run",
        sa.Column("id", AutoString(length=64), nullable=False),
        sa.Column("cycle", AutoString(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "request_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("queued_run", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_queued_run_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_queued_run_cycle"), ["cycle"], unique=False)

    op.create_table(
        "reportarchive",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cycle_name", AutoString(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=False),
        sa.Column(
            "summary_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("artifact_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("total_tests", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=True),
        sa.Column("failed", sa.Integer(), nullable=True),
        sa.Column("broken", sa.Integer(), nullable=True),
        sa.Column("skipped", sa.Integer(), nullable=True),
        sa.Column("unknown", sa.Integer(), nullable=True),
        sa.Column("allure_duration_ms", sa.Integer(), nullable=True),
        sa.Column("plan_duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("reportarchive", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_reportarchive_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_reportarchive_cycle_name"), ["cycle_name"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_reportarchive_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_reportarchive_plan_duration_ms"), ["plan_duration_ms"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_reportarchive_total_tests"), ["total_tests"], unique=False
        )

    op.create_table(
        "resource_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", sa.Float(), nullable=False),
        sa.Column("pool", AutoString(length=128), nullable=False),
        sa.Column("item", AutoString(length=128), nullable=False),
        sa.Column("verb", AutoString(length=16), nullable=False),
        sa.Column("user", AutoString(length=64), nullable=False),
        sa.Column("host", AutoString(length=255), nullable=False),
        sa.Column("command", AutoString(length=500), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("detail", AutoString(length=500), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("resource_action", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_resource_action_at"), ["at"], unique=False)
        batch_op.create_index(batch_op.f("ix_resource_action_pool"), ["pool"], unique=False)

    op.create_table(
        "resource_item",
        sa.Column("pool", AutoString(length=128), nullable=False),
        sa.Column("item", AutoString(length=128), nullable=False),
        sa.Column(
            "labels",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "data",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("disabled_reason", AutoString(length=500), nullable=False),
        sa.Column("disabled_by", AutoString(length=64), nullable=True),
        sa.Column("seen_at", sa.Float(), nullable=False),
        sa.Column("clean", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("pool", "item"),
    )
    op.create_table(
        "resource_lease",
        sa.Column("pool", AutoString(length=128), nullable=False),
        sa.Column("item", AutoString(length=128), nullable=False),
        sa.Column("lease_id", AutoString(length=64), nullable=False),
        sa.Column("holder_user", AutoString(length=64), nullable=False),
        sa.Column("holder_host", AutoString(length=255), nullable=False),
        sa.Column("holder_pid", sa.Integer(), nullable=False),
        sa.Column("run_id", AutoString(length=128), nullable=False),
        sa.Column("stage", AutoString(length=128), nullable=False),
        sa.Column("worker", AutoString(length=64), nullable=False),
        sa.Column("note", AutoString(length=200), nullable=False),
        sa.Column("taken_at", sa.Float(), nullable=False),
        sa.Column("heartbeat_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("ttl_s", sa.Float(), nullable=False),
        sa.Column("reuse_delay_s", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("pool", "item"),
    )
    with op.batch_alter_table("resource_lease", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_resource_lease_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_resource_lease_lease_id"), ["lease_id"], unique=True)

    op.create_table(
        "resource_waiter",
        sa.Column("id", AutoString(length=64), nullable=False),
        sa.Column("pool", AutoString(length=128), nullable=False),
        sa.Column(
            "candidates",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("holder_user", AutoString(length=64), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("heartbeat_at", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("resource_waiter", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_resource_waiter_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_resource_waiter_pool"), ["pool"], unique=False)

    op.create_table(
        "runrecord",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="runstatus"),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("runrecord", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_runrecord_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_runrecord_status"), ["status"], unique=False)

    op.create_table(
        "user_account",
        sa.Column("username", AutoString(length=64), nullable=False),
        sa.Column("password_hash", AutoString(length=512), nullable=False),
        sa.Column("role", AutoString(length=16), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("username"),
    )


def downgrade() -> None:
    op.drop_table("user_account")
    with op.batch_alter_table("runrecord", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_runrecord_status"))
        batch_op.drop_index(batch_op.f("ix_runrecord_id"))

    op.drop_table("runrecord")
    with op.batch_alter_table("resource_waiter", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resource_waiter_pool"))
        batch_op.drop_index(batch_op.f("ix_resource_waiter_created_at"))

    op.drop_table("resource_waiter")
    with op.batch_alter_table("resource_lease", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resource_lease_lease_id"))
        batch_op.drop_index(batch_op.f("ix_resource_lease_expires_at"))

    op.drop_table("resource_lease")
    op.drop_table("resource_item")
    with op.batch_alter_table("resource_action", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resource_action_pool"))
        batch_op.drop_index(batch_op.f("ix_resource_action_at"))

    op.drop_table("resource_action")
    with op.batch_alter_table("reportarchive", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reportarchive_total_tests"))
        batch_op.drop_index(batch_op.f("ix_reportarchive_plan_duration_ms"))
        batch_op.drop_index(batch_op.f("ix_reportarchive_id"))
        batch_op.drop_index(batch_op.f("ix_reportarchive_cycle_name"))
        batch_op.drop_index(batch_op.f("ix_reportarchive_created_at"))

    op.drop_table("reportarchive")
    with op.batch_alter_table("queued_run", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_queued_run_cycle"))
        batch_op.drop_index(batch_op.f("ix_queued_run_created_at"))

    op.drop_table("queued_run")
    with op.batch_alter_table("failure_triage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_failure_triage_cycle"))

    op.drop_table("failure_triage")
    with op.batch_alter_table("audit_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_event_username"))
        batch_op.drop_index(batch_op.f("ix_audit_event_at"))

    op.drop_table("audit_event")
