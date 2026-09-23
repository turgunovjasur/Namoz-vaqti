"""Add personal reminders and occurrence reservations.

Revision ID: 20260923_01
Revises: 20260826_04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260923_01"
down_revision: str | None = "20260826_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("at", sa.String(5), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=True),
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
        sa.Column("next_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("creation_token", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "creation_token", name="uq_reminder_creation"),
        sa.CheckConstraint("kind IN ('once', 'daily', 'weekly')", name="ck_reminder_kind"),
        sa.CheckConstraint(
            "status IN ('active', 'processing', 'completed', 'failed', 'paused')",
            name="ck_reminder_status",
        ),
        sa.CheckConstraint(
            "(kind = 'once' AND on_date IS NOT NULL AND weekday IS NULL) OR "
            "(kind = 'daily' AND on_date IS NULL AND weekday IS NULL) OR "
            "(kind = 'weekly' AND on_date IS NULL AND weekday BETWEEN 0 AND 6 "
            "AND weekday IS NOT NULL)",
            name="ck_reminder_schedule",
        ),
    )
    for column in ("user_id", "next_due", "status"):
        op.create_index(f"ix_reminders_{column}", "reminders", [column])
    op.create_table(
        "reminder_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reminder_id",
            sa.Integer(),
            sa.ForeignKey("reminders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.UniqueConstraint("reminder_id", "scheduled_at", name="uq_reminder_occurrence"),
    )


def downgrade() -> None:
    op.drop_table("reminder_deliveries")
    op.drop_table("reminders")
