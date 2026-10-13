"""Durable main-agent conversations and request receipts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261013_01"
down_revision: str | None = "20261012_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_sessions_expires_at", "agent_sessions", ["expires_at"])
    op.create_table(
        "agent_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_id", name="uq_agent_request"),
    )
    op.create_index("ix_agent_receipts_user_id", "agent_receipts", ["user_id"])
    op.create_index("ix_agent_receipts_created_at", "agent_receipts", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_receipts")
    op.drop_table("agent_sessions")
