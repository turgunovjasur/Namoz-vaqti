"""SQLAlchemy persistence schema."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    region_code: Mapped[str] = mapped_column(String(100), default="Toshkent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
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
