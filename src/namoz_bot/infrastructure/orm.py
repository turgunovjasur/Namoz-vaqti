"""SQLAlchemy persistence schema."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
