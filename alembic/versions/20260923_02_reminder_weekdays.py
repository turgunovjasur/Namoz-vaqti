"""Support multiple weekdays on one reminder, preserving existing schedules."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260923_02"
down_revision: str | None = "20260923_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reminders", sa.Column("weekdays_mask", sa.SmallInteger(), nullable=True))
    op.execute("UPDATE reminders SET weekdays_mask = (1 << weekday) WHERE kind = 'weekly'")
    op.drop_constraint("ck_reminder_schedule", "reminders", type_="check")
    op.drop_column("reminders", "weekday")
    op.create_check_constraint(
        "ck_reminder_schedule",
        "reminders",
        "(kind = 'once' AND on_date IS NOT NULL AND weekdays_mask IS NULL) OR "
        "(kind = 'daily' AND on_date IS NULL AND weekdays_mask IS NULL) OR "
        "(kind = 'weekly' AND on_date IS NULL AND weekdays_mask BETWEEN 1 AND 127 "
        "AND weekdays_mask IS NOT NULL)",
    )


def downgrade() -> None:
    multiple = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM reminders WHERE kind = 'weekly' "
            "AND weekdays_mask NOT IN (1, 2, 4, 8, 16, 32, 64)"
        )
    )
    if multiple:
        raise RuntimeError("Cannot downgrade while multi-day reminders exist; no data was changed.")
    op.add_column("reminders", sa.Column("weekday", sa.SmallInteger(), nullable=True))
    op.execute(
        "UPDATE reminders SET weekday = CASE weekdays_mask "
        "WHEN 1 THEN 0 WHEN 2 THEN 1 WHEN 4 THEN 2 WHEN 8 THEN 3 "
        "WHEN 16 THEN 4 WHEN 32 THEN 5 WHEN 64 THEN 6 END WHERE kind = 'weekly'"
    )
    op.drop_constraint("ck_reminder_schedule", "reminders", type_="check")
    op.drop_column("reminders", "weekdays_mask")
    op.create_check_constraint(
        "ck_reminder_schedule",
        "reminders",
        "(kind = 'once' AND on_date IS NOT NULL AND weekday IS NULL) OR "
        "(kind = 'daily' AND on_date IS NULL AND weekday IS NULL) OR "
        "(kind = 'weekly' AND on_date IS NULL AND weekday BETWEEN 0 AND 6 "
        "AND weekday IS NOT NULL)",
    )
