"""Align existing personal religious reminder schedules to full hours."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261009_02"
down_revision: str | None = "20261009_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy fractional intervals are rounded up; users' enabled/off choices stay intact.
    op.execute("UPDATE religious_intervals SET interval_hours = CEIL(interval_hours)")
    op.execute(
        "UPDATE religious_intervals SET next_due = date_trunc('hour', next_due) "
        "WHERE next_due IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_religious_interval_whole_hours",
        "religious_intervals",
        "interval_hours = CAST(interval_hours AS INTEGER)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_religious_interval_whole_hours", "religious_intervals", type_="check")
