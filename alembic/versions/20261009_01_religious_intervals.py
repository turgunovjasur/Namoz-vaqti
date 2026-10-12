"""Store personal nasihat intervals without changing existing user settings."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_01"
down_revision: str | None = "20260923_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "religious_intervals",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("interval_hours", sa.Float(), nullable=False),
        sa.Column("next_due", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("interval_hours BETWEEN 0 AND 168", name="ck_religious_interval_range"),
        sa.CheckConstraint(
            "(interval_hours = 0 AND next_due IS NULL) OR "
            "(interval_hours > 0 AND next_due IS NOT NULL)",
            name="ck_religious_interval_due",
        ),
    )
    op.create_index("ix_religious_intervals_next_due", "religious_intervals", ["next_due"])


def downgrade() -> None:
    op.drop_table("religious_intervals")
