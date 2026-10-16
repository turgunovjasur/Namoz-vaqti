"""SQLAlchemy persistence schema."""

from datetime import date, datetime

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from namoz_bot.domain.models import DeliveryStatus, DeliveryType


class Base(DeclarativeBase):
    """Declarative metadata root."""


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = tuple(
        CheckConstraint(
            f"{prayer}_offset BETWEEN -30 AND 30",
            name=f"ck_users_{prayer}_offset_range",
        )
        for prayer in ("bomdod", "quyosh", "peshin", "asr", "shom", "xufton")
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(256))
    username: Mapped[str | None] = mapped_column(String(64))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    region_code: Mapped[str] = mapped_column(String(100), default="Toshkent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    bomdod_offset: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    quyosh_offset: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    peshin_offset: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    asr_offset: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    shom_offset: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    xufton_offset: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deliveries: Mapped[list["DeliveryRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class DailyScheduleRecord(Base):
    __tablename__ = "daily_schedule_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    at: Mapped[str] = mapped_column(String(5))
    next_due: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReligiousIntervalRecord(Base):
    __tablename__ = "religious_intervals"
    __table_args__ = (
        CheckConstraint("interval_hours BETWEEN 0 AND 168", name="ck_religious_interval_range"),
        CheckConstraint(
            "interval_hours = CAST(interval_hours AS INTEGER)",
            name="ck_religious_interval_whole_hours",
        ),
        CheckConstraint(
            "(interval_hours = 0 AND next_due IS NULL) OR "
            "(interval_hours > 0 AND next_due IS NOT NULL)",
            name="ck_religious_interval_due",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    interval_hours: Mapped[float] = mapped_column(Float)
    next_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class DeliveryRecord(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "schedule_date", "delivery_type", name="uq_delivery_user_date_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    schedule_date: Mapped[date] = mapped_column(Date)
    delivery_type: Mapped[str] = mapped_column(String(20), default=DeliveryType.DAILY.value)
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.PENDING.value)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user: Mapped[UserRecord] = relationship(back_populates="deliveries")


class ReminderRecord(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        UniqueConstraint("user_id", "creation_token", name="uq_reminder_creation"),
        CheckConstraint("kind IN ('once', 'daily', 'weekly')", name="ck_reminder_kind"),
        CheckConstraint(
            "status IN ('active', 'processing', 'completed', 'failed', 'paused')",
            name="ck_reminder_status",
        ),
        CheckConstraint(
            "(kind = 'once' AND on_date IS NOT NULL AND weekdays_mask IS NULL) OR "
            "(kind = 'daily' AND on_date IS NULL AND weekdays_mask IS NULL) OR "
            "(kind = 'weekly' AND on_date IS NULL AND weekdays_mask BETWEEN 1 AND 127 "
            "AND weekdays_mask IS NOT NULL)",
            name="ck_reminder_schedule",
        ),
        {"sqlite_autoincrement": True},
    )

    record_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(String(1000))
    at: Mapped[str] = mapped_column(String(5))
    kind: Mapped[str] = mapped_column(String(10))
    on_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekdays_mask: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    next_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    creation_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReminderDeliveryRecord(Base):
    __tablename__ = "reminder_deliveries"
    __table_args__ = (
        UniqueConstraint("reminder_id", "scheduled_at", name="uq_reminder_occurrence"),
        {"sqlite_autoincrement": True},
    )

    record_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)


class FinanceEntryRecord(Base):
    __tablename__ = "finance_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "source_key", name="uq_finance_source"),
        CheckConstraint("kind IN ('income', 'expense')", name="ck_finance_kind"),
        CheckConstraint("amount BETWEEN 1 AND 1000000000000000", name="ck_finance_amount"),
        Index("ix_finance_owner_period", "user_id", "period"),
        Index("ix_finance_owner_history", "user_id", "id"),
        {"sqlite_autoincrement": True},
    )

    record_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("finance_entries.id"), nullable=True
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    amount: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(300))
    period: Mapped[date] = mapped_column(Date)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_key: Mapped[str] = mapped_column(String(64))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSessionRecord(Base):
    __tablename__ = "agent_sessions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    state: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AgentReceiptRecord(Base):
    __tablename__ = "agent_receipts"
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_agent_request"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    result: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProfileRecord(Base):
    __tablename__ = "profiles"
    __table_args__ = (CheckConstraint("profile_type IN ('admin','user')", name="ck_profile_type"),)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    profile_type: Mapped[str] = mapped_column(String(10), default="user", server_default="user")


class RoleAssignmentRecord(Base):
    __tablename__ = "user_role_assignments"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class RoleCapabilityRecord(Base):
    __tablename__ = "user_role_capabilities"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    capability_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class RoleModelRecord(Base):
    __tablename__ = "role_model_settings"
    role_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class AdminAuditRecord(Base):
    __tablename__ = "admin_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32))
    detail: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkforceTaskRecord(Base):
    __tablename__ = "workforce_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "bot_id", "request_id", name="uq_workforce_input"),
    )
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    request_id: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    lease_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkforceRevisionRecord(Base):
    __tablename__ = "workforce_task_revisions"
    task_id: Mapped[str] = mapped_column(
        ForeignKey("workforce_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    plan: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    service_result: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    review: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    review_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class WorkforceOutboxRecord(Base):
    __tablename__ = "workforce_outbox"
    __table_args__ = (
        UniqueConstraint("task_id", "revision", "kind", name="uq_workforce_notification"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("workforce_tasks.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    lease_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WorkforceUpdateRecord(Base):
    __tablename__ = "workforce_updates"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))


class CorrectionAuditRecord(Base):
    __tablename__ = "workforce_correction_audit"
    __table_args__ = (UniqueConstraint("user_id", "source_key", name="uq_correction_source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    original_id: Mapped[int] = mapped_column(Integer)
    replacement_id: Mapped[int] = mapped_column(Integer)
    before: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    after: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminLoginTicketRecord(Base):
    __tablename__ = "admin_login_tickets"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdminWebSessionRecord(Base):
    __tablename__ = "admin_web_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AgentRoleRecord(Base):
    __tablename__ = "agent_roles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(String(2000))
    common_rules: Mapped[str] = mapped_column(String(8000))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    system_role: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class AgentRoleSkillRecord(Base):
    __tablename__ = "agent_role_skills"
    role_id: Mapped[str] = mapped_column(
        ForeignKey("agent_roles.id", ondelete="CASCADE"), primary_key=True
    )
    capability_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class AgentRuleTemplateRecord(Base):
    __tablename__ = "agent_rule_templates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rules: Mapped[str] = mapped_column(String(8000))
    revision: Mapped[int] = mapped_column(Integer, default=1)
