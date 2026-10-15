"""Admin web authentication and trusted Telegram identity metadata. No grant changes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_04"
down_revision: str | None = "20261015_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(256), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    for table in ("admin_login_tickets", "admin_web_sessions"):
        op.create_table(
            table,
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_index(f"ix_{table}_expires_at", table, ["expires_at"])


def downgrade() -> None:
    for table in ("admin_web_sessions", "admin_login_tickets"):
        op.drop_table(table)
    op.drop_column("users", "username")
    op.drop_column("users", "display_name")
