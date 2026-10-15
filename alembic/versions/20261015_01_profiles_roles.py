"""Profiles and explicit per-user, per-role capability grants."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_01"
down_revision: str | None = "20261013_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Immutable migration catalog. New capabilities never join old grants implicitly.
LEGACY = {
    "prayer": (
        "prayer.schedule",
        "prayer.set_region",
        "prayer.set_offset",
        "prayer.reset_offsets",
        "preferences.region_view",
        "preferences.offsets_view",
    ),
    "nasihat": (
        "nasihat.excerpt",
        "nasihat.settings_view",
        "nasihat.set_interval",
        "nasihat.deliver",
    ),
    "reminder": ("reminder.create", "reminder.list", "reminder.delete", "reminder.deliver"),
    "accounting": (
        "finance.income",
        "finance.expense",
        "finance.balance",
        "finance.report",
        "finance.history",
        "finance.undo",
    ),
    "settings": (
        "settings.open",
        "settings.set_daily",
        "settings.deliver_daily",
        "preferences.region_view",
        "preferences.offsets_view",
    ),
}


def owner(*, primary: bool = True) -> sa.Column:
    return sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=primary,
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "profiles",
        owner(),
        sa.Column("profile_type", sa.String(10), nullable=False, server_default="user"),
        sa.CheckConstraint("profile_type IN ('admin','user')", name="ck_profile_type"),
    )
    op.create_table(
        "user_role_assignments",
        owner(),
        sa.Column("role_id", sa.String(32), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "user_role_capabilities",
        owner(),
        sa.Column("role_id", sa.String(32), primary_key=True),
        sa.Column("capability_id", sa.String(64), primary_key=True),
    )
    op.create_table(
        "role_model_settings",
        sa.Column("role_id", sa.String(32), primary_key=True),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "admin_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    conn = op.get_bind()
    conn.execute(sa.text("INSERT INTO profiles (user_id,profile_type) SELECT id,'user' FROM users"))
    for role_id, capabilities in LEGACY.items():
        conn.execute(
            sa.text(
                "INSERT INTO user_role_assignments (user_id,role_id,enabled,revision) "
                "SELECT id,:role,true,1 FROM users"
            ),
            {"role": role_id},
        )
        for capability_id in capabilities:
            conn.execute(
                sa.text(
                    "INSERT INTO user_role_capabilities (user_id,role_id,capability_id) "
                    "SELECT id,:role,:cap FROM users"
                ),
                {"role": role_id, "cap": capability_id},
            )


def downgrade() -> None:
    for table in (
        "admin_audit",
        "role_model_settings",
        "user_role_capabilities",
        "user_role_assignments",
        "profiles",
    ):
        op.drop_table(table)
