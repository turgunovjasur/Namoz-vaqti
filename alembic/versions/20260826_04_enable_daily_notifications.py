"""Enable daily notifications for all existing users.

Revision ID: 20260826_04
Revises: 20260826_03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_04"
down_revision: str | None = "20260826_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    users = sa.table("users", sa.column("is_active", sa.Boolean()))
    op.execute(users.update().where(users.c.is_active.is_(False)).values(is_active=True))


def downgrade() -> None:
    # Previous opt-out choices cannot be reconstructed after all users are enabled.
    pass
