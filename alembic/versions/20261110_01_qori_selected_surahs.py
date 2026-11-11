"""Store each user's selected surahs."""

import sqlalchemy as sa

from alembic import op

revision = "20261110_01"
down_revision = "20261104_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qori_selected_surahs",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("chapter", sa.SmallInteger(), primary_key=True),
        sa.CheckConstraint("chapter BETWEEN 1 AND 114", name="ck_qori_chapter_range"),
    )


def downgrade() -> None:
    op.drop_table("qori_selected_surahs")
