"""Personal whole-so'm income and expense journal."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_01"
down_revision: str | None = "20261009_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "source_key", name="uq_finance_source"),
        sa.CheckConstraint("kind IN ('income', 'expense')", name="ck_finance_kind"),
        sa.CheckConstraint("amount BETWEEN 1 AND 1000000000000000", name="ck_finance_amount"),
    )
    op.create_index("ix_finance_owner_period", "finance_entries", ["user_id", "period"])
    op.create_index("ix_finance_owner_history", "finance_entries", ["user_id", "id"])


def downgrade() -> None:
    op.drop_table("finance_entries")
