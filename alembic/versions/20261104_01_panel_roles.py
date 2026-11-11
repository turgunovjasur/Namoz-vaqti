"""Retire the old manager; preserve configured roles and allow archival."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261104_01"
down_revision: str | None = "20261016_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_roles",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    connection = op.get_bind()
    # A pristine installation passed through the historical seed migration.
    # Never remove data from an installation which already has users or edits.
    pristine = (
        not connection.scalar(sa.text("SELECT count(*) FROM users"))
        and not connection.scalar(sa.text("SELECT count(*) FROM admin_audit"))
        and not connection.scalar(sa.text("SELECT count(*) FROM role_model_settings"))
    )
    if pristine:
        connection.execute(sa.text("DELETE FROM agent_role_skills WHERE role_id != 'assistant'"))
        connection.execute(sa.text("DELETE FROM agent_roles WHERE id != 'assistant'"))
    else:
        connection.execute(
            sa.text(
                "UPDATE agent_roles SET archived=true, enabled=false "
                "WHERE id='manager' AND system_role=true"
            )
        )


def downgrade() -> None:
    op.drop_column("agent_roles", "archived")
