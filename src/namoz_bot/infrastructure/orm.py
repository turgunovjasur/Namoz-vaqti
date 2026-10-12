"""SQLAlchemy persistence schema."""

from datetime import date, datetime

from sqlalchemy import (
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
