"""SQLAlchemy implementations of application persistence ports."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from namoz_bot.domain.errors import SubscriptionNotFoundError
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    UserSubscription,
)
from namoz_bot.infrastructure.orm import DeliveryRecord, UserRecord


def _to_subscription(record: UserRecord) -> UserSubscription:
    return UserSubscription(
        id=record.id,
        telegram_user_id=record.telegram_user_id,
        chat_id=record.chat_id,
        region_code=record.region_code,
        is_active=record.is_active,
    )


class SqlAlchemySubscriptionRepository:
    """Store subscription entities in one SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None:
        record = await self._session.scalar(
            select(UserRecord).where(UserRecord.telegram_user_id == telegram_user_id)
        )
        return None if record is None else _to_subscription(record)

    async def add(self, subscription: UserSubscription) -> UserSubscription:
        record = UserRecord(
            telegram_user_id=subscription.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=subscription.region_code,
            is_active=subscription.is_active,
        )
        self._session.add(record)
        await self._session.flush()
        return _to_subscription(record)

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        record = await self._session.scalar(
            select(UserRecord).where(UserRecord.telegram_user_id == subscription.telegram_user_id)
        )
        if record is None:
            raise SubscriptionNotFoundError(
                f"Telegram foydalanuvchisi topilmadi: {subscription.telegram_user_id}"
            )
        record.chat_id = subscription.chat_id
        record.region_code = subscription.region_code
        record.is_active = subscription.is_active
        await self._session.flush()
        return _to_subscription(record)

    async def list_active(self) -> list[UserSubscription]:
        records = (
            await self._session.scalars(
                select(UserRecord).where(UserRecord.is_active.is_(True)).order_by(UserRecord.id)
            )
        ).all()
        return [_to_subscription(record) for record in records]


class SqlAlchemyDeliveryRepository:
    """Track daily delivery status in one SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
    ) -> bool:
        record = await self._find(user_id, schedule_date, delivery_type)
        if record is None:
            self._session.add(
                DeliveryRecord(
                    user_id=user_id,
                    schedule_date=schedule_date,
                    delivery_type=delivery_type.value,
                    status=DeliveryStatus.PENDING.value,
                )
            )
            await self._session.flush()
            return True
        if record.status == DeliveryStatus.SENT.value:
            return False
        record.status = DeliveryStatus.PENDING.value
        record.error_code = None
        await self._session.flush()
        return True

    async def mark_status(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
        status: DeliveryStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        record = await self._find(user_id, schedule_date, delivery_type)
        if record is None:
            raise LookupError("Yuborish rezervatsiyasi topilmadi")
        record.status = status.value
        record.error_code = error_code
        record.sent_at = datetime.now(UTC) if status is DeliveryStatus.SENT else None
        await self._session.flush()

    async def _find(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
    ) -> DeliveryRecord | None:
        record: DeliveryRecord | None = await self._session.scalar(
            select(DeliveryRecord).where(
                DeliveryRecord.user_id == user_id,
                DeliveryRecord.schedule_date == schedule_date,
                DeliveryRecord.delivery_type == delivery_type.value,
            )
        )
        return record
