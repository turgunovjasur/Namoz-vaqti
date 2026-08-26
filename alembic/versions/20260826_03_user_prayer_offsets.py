"""Add per-user prayer time offsets.

Revision ID: 20260826_03
Revises: 20260826_02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_03"
down_revision: str | None = "20260826_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRAYERS = ("bomdod", "quyosh", "peshin", "asr", "shom", "xufton")


def upgrade() -> None:
    for prayer in PRAYERS:
        column_name = f"{prayer}_offset"
        op.add_column(
            "users",
            sa.Column(
                column_name,
                sa.SmallInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        op.create_check_constraint(
            f"ck_users_{prayer}_offset_range",
            "users",
            f"{column_name} BETWEEN -30 AND 30",
        )


def downgrade() -> None:
    for prayer in reversed(PRAYERS):
        op.drop_constraint(
            f"ck_users_{prayer}_offset_range",
            "users",
            type_="check",
        )
        op.drop_column("users", f"{prayer}_offset")
