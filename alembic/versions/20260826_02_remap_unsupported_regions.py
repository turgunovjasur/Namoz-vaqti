"""Remap region codes unsupported by the new prayer-time provider.

Revision ID: 20260826_02
Revises: 20260826_01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_02"
down_revision: str | None = "20260826_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_UNSUPPORTED_REGIONS = (
    "O'smat",
    "Uzunquduq",
    "Tallimarj\u043en",
    "O'g'iz",
    "Gazli",
    "Burchmulla",
)


def upgrade() -> None:
    users = sa.table("users", sa.column("region_code", sa.String(length=100)))
    op.execute(
        users.update()
        .where(users.c.region_code.in_(LEGACY_UNSUPPORTED_REGIONS))
        .values(region_code="Toshkent")
    )


def downgrade() -> None:
    # The six original values cannot be reconstructed after their rows are merged.
    pass
