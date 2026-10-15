"""Versioned original records and atomic correction history. No new grants."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_03"
down_revision: str | None = "20261015_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("finance_entries", "reminders", "reminder_deliveries"):
        op.add_column(
            table, sa.Column("record_revision", sa.Integer(), nullable=False, server_default="0")
        )
    op.add_column(
        "finance_entries",
        sa.Column(
            "supersedes_id",
            sa.Integer(),
            sa.ForeignKey("finance_entries.id", name="fk_finance_supersedes"),
        ),
    )
    op.create_table(
        "workforce_correction_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("original_id", sa.Integer(), nullable=False),
        sa.Column("replacement_id", sa.Integer(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "source_key", name="uq_correction_source"),
    )


def downgrade() -> None:
    op.drop_table("workforce_correction_audit")
    op.drop_column("finance_entries", "supersedes_id")
    for table in ("reminder_deliveries", "reminders", "finance_entries"):
        op.drop_column(table, "record_revision")
