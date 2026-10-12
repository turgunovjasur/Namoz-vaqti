"""Persist each user's preferred daily schedule send time."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_03"
down_revision: str | None = "20261009_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_schedule_preferences",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("at", sa.String(5), nullable=False),
        sa.Column("next_due", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_daily_schedule_preferences_next_due", "daily_schedule_preferences", ["next_due"]
    )


def downgrade() -> None:
    op.drop_table("daily_schedule_preferences")
