"""Durable task revisions, effect receipts, leases and delivery outbox."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_02"
down_revision: str | None = "20261015_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workforce_tasks",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("lease_token", sa.String(32)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "bot_id", "request_id", name="uq_workforce_input"),
    )
    for name in ("user_id", "status", "lease_until"):
        op.create_index(f"ix_workforce_tasks_{name}", "workforce_tasks", [name])
    op.create_table(
        "workforce_task_revisions",
        sa.Column(
            "task_id",
            sa.String(20),
            sa.ForeignKey("workforce_tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("service_result", sa.JSON()),
        sa.Column("review", sa.JSON()),
        sa.Column("feedback", sa.String(2000)),
        sa.Column("review_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "workforce_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(20),
            sa.ForeignKey("workforce_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("lease_token", sa.String(32)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "revision", "kind", name="uq_workforce_notification"),
    )
    for name in ("status", "next_attempt"):
        op.create_index(f"ix_workforce_outbox_{name}", "workforce_outbox", [name])
    op.create_table(
        "workforce_updates",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("bot_id", sa.BigInteger(), primary_key=True),
        sa.Column("request_id", sa.String(100), primary_key=True),
        sa.Column("task_id", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "workforce_updates",
        "workforce_outbox",
        "workforce_task_revisions",
        "workforce_tasks",
    ):
        op.drop_table(table)
