"""Short-transaction SQLAlchemy implementations of persistence ports."""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.errors import ScheduleValidationError, SubscriptionNotFoundError
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    OffsetAction,
    PrayerKey,
    PrayerOffsets,
    UserSubscription,
)
from namoz_bot.infrastructure.orm import DeliveryRecord, UserRecord


def _offset_column_name(prayer: PrayerKey) -> str:
    match prayer:
        case "bomdod":
            return "bomdod_offset"
        case "quyosh":
            return "quyosh_offset"
        case "peshin":
            return "peshin_offset"
        case "asr":
            return "asr_offset"
        case "shom":
            return "shom_offset"
        case "xufton":
            return "xufton_offset"
        case _:
            raise ScheduleValidationError("Sozlanadigan vaqt topilmadi")


def _offset_values(offsets: PrayerOffsets) -> dict[str, int]:
    return {
        "bomdod_offset": offsets.bomdod,
        "quyosh_offset": offsets.quyosh,
        "peshin_offset": offsets.peshin,
        "asr_offset": offsets.asr,
        "shom_offset": offsets.shom,
        "xufton_offset": offsets.xufton,
    }


def _to_subscription(record: UserRecord) -> UserSubscription:
    return UserSubscription(
        id=record.id,
        telegram_user_id=record.telegram_user_id,
        chat_id=record.chat_id,
        region_code=record.region_code,
        is_active=record.is_active,
        offsets=PrayerOffsets(
            bomdod=record.bomdod_offset,
            quyosh=record.quyosh_offset,
            peshin=record.peshin_offset,
            asr=record.asr_offset,
            shom=record.shom_offset,
            xufton=record.xufton_offset,
        ),
    )


def _dialect_name(session: AsyncSession) -> str:
    return session.get_bind().dialect.name


class SqlAlchemySubscriptionRepository:
    """Persist each subscription operation in its own short transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(UserRecord).where(UserRecord.telegram_user_id == telegram_user_id)
            )
            return None if record is None else _to_subscription(record)

    async def add(self, subscription: UserSubscription) -> UserSubscription:
        async with self._session_factory.begin() as session:
            record = UserRecord(
                telegram_user_id=subscription.telegram_user_id,
                chat_id=subscription.chat_id,
                region_code=subscription.region_code,
                is_active=subscription.is_active,
                **_offset_values(subscription.offsets),
            )
            session.add(record)
            await session.flush()
            return _to_subscription(record)

    async def upsert_start(
        self,
        subscription: UserSubscription,
    ) -> tuple[UserSubscription, bool]:
        """Create or reactivate a Telegram user without a uniqueness race."""

        async with self._session_factory.begin() as session:
            values = {
                "telegram_user_id": subscription.telegram_user_id,
                "chat_id": subscription.chat_id,
                "region_code": subscription.region_code,
                "is_active": True,
                **_offset_values(subscription.offsets),
            }
            statement: Any
            if _dialect_name(session) == "postgresql":
                statement = (
                    postgresql_insert(UserRecord)
                    .values(**values)
                    .on_conflict_do_nothing(
                        index_elements=[UserRecord.telegram_user_id],
                    )
                    .returning(UserRecord)
                )
            elif _dialect_name(session) == "sqlite":
                statement = (
                    sqlite_insert(UserRecord)
                    .values(**values)
                    .on_conflict_do_nothing(
                        index_elements=[UserRecord.telegram_user_id],
                    )
                    .returning(UserRecord)
                )
            else:
                raise RuntimeError("Faqat PostgreSQL va test SQLite dialektlari qo‘llanadi")

            inserted = (await session.execute(statement)).scalar_one_or_none()
            if inserted is not None:
                return _to_subscription(inserted), True

            reactivated = await session.scalar(
                update(UserRecord)
                .where(UserRecord.telegram_user_id == subscription.telegram_user_id)
                .values(
                    chat_id=subscription.chat_id,
                    is_active=True,
                    updated_at=datetime.now(UTC),
                )
                .returning(UserRecord)
            )
            if reactivated is None:
                raise LookupError("Foydalanuvchi upsert natijasi topilmadi")
            return _to_subscription(reactivated), False

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        async with self._session_factory.begin() as session:
            record = await session.scalar(
                select(UserRecord).where(
                    UserRecord.telegram_user_id == subscription.telegram_user_id
                )
            )
            if record is None:
                raise SubscriptionNotFoundError(
                    f"Telegram foydalanuvchisi topilmadi: {subscription.telegram_user_id}"
                )
            record.chat_id = subscription.chat_id
            record.region_code = subscription.region_code
            record.is_active = subscription.is_active
            record.bomdod_offset = subscription.offsets.bomdod
            record.quyosh_offset = subscription.offsets.quyosh
            record.peshin_offset = subscription.offsets.peshin
            record.asr_offset = subscription.offsets.asr
            record.shom_offset = subscription.offsets.shom
            record.xufton_offset = subscription.offsets.xufton
            await session.flush()
            return _to_subscription(record)

    async def change_offset(
        self,
        telegram_user_id: int,
        prayer: PrayerKey,
        action: OffsetAction,
    ) -> UserSubscription:
        """Atomically update one offset without overwriting other preferences."""

        if isinstance(action, bool) or action not in (-1, 0, 1):
            raise ScheduleValidationError("Offset amali noto‘g‘ri")
        column_name = _offset_column_name(prayer)
        column = getattr(UserRecord, column_name)
        value = 0 if action == 0 else column + action
        statement = update(UserRecord).where(UserRecord.telegram_user_id == telegram_user_id)
        if action > 0:
            statement = statement.where(column < 30)
        elif action < 0:
            statement = statement.where(column > -30)
        statement = statement.values(
            **{
                column_name: value,
                "updated_at": datetime.now(UTC),
            }
        ).returning(UserRecord)

        async with self._session_factory.begin() as session:
            record = await session.scalar(statement)
            if record is not None:
                return _to_subscription(record)
            exists = await session.scalar(
                select(UserRecord.id).where(UserRecord.telegram_user_id == telegram_user_id)
            )
            if exists is None:
                raise SubscriptionNotFoundError(
                    f"Telegram foydalanuvchisi topilmadi: {telegram_user_id}"
                )
            raise ScheduleValidationError("Offset farqi chegaraga yetgan")

    async def change_region(
        self,
        telegram_user_id: int,
        region_code: str,
    ) -> UserSubscription:
        """Atomically replace the region and reset every old-region offset."""

        async with self._session_factory.begin() as session:
            record = await session.scalar(
                update(UserRecord)
                .where(UserRecord.telegram_user_id == telegram_user_id)
                .values(
                    region_code=region_code,
                    bomdod_offset=0,
                    quyosh_offset=0,
                    peshin_offset=0,
                    asr_offset=0,
                    shom_offset=0,
                    xufton_offset=0,
                    updated_at=datetime.now(UTC),
                )
                .returning(UserRecord)
            )
            if record is None:
                raise SubscriptionNotFoundError(
                    f"Telegram foydalanuvchisi topilmadi: {telegram_user_id}"
                )
            return _to_subscription(record)

    async def set_active(
        self,
        telegram_user_id: int,
        active: bool,
    ) -> UserSubscription:
        """Update notification state without touching region or offsets."""

        async with self._session_factory.begin() as session:
            record = await session.scalar(
                update(UserRecord)
                .where(UserRecord.telegram_user_id == telegram_user_id)
                .values(is_active=active, updated_at=datetime.now(UTC))
                .returning(UserRecord)
            )
            if record is None:
                raise SubscriptionNotFoundError(
                    f"Telegram foydalanuvchisi topilmadi: {telegram_user_id}"
                )
            return _to_subscription(record)

    async def list_active_page(
        self,
        *,
        after_id: int,
        limit: int,
    ) -> list[UserSubscription]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(UserRecord)
                    .where(UserRecord.is_active.is_(True), UserRecord.id > after_id)
                    .order_by(UserRecord.id)
                    .limit(limit)
                )
            ).all()
            return [_to_subscription(record) for record in records]


class SqlAlchemyDeliveryRepository:
    """Atomically claim delivery attempts and persist each result immediately."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def claim_batch(
        self,
        user_ids: list[int],
        schedule_date: date,
        delivery_type: DeliveryType,
    ) -> set[int]:
        if not user_ids:
            return set()

        values = [
            {
                "user_id": user_id,
                "schedule_date": schedule_date,
                "delivery_type": delivery_type.value,
                "status": DeliveryStatus.PENDING.value,
            }
            for user_id in user_ids
        ]
        async with self._session_factory.begin() as session:
            statement: Any
            if _dialect_name(session) == "postgresql":
                statement = (
                    postgresql_insert(DeliveryRecord)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=[
                            DeliveryRecord.user_id,
                            DeliveryRecord.schedule_date,
                            DeliveryRecord.delivery_type,
                        ]
                    )
                    .returning(DeliveryRecord.user_id)
                )
            elif _dialect_name(session) == "sqlite":
                statement = (
                    sqlite_insert(DeliveryRecord)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=[
                            DeliveryRecord.user_id,
                            DeliveryRecord.schedule_date,
                            DeliveryRecord.delivery_type,
                        ]
                    )
                    .returning(DeliveryRecord.user_id)
                )
            else:
                raise RuntimeError("Faqat PostgreSQL va test SQLite dialektlari qo‘llanadi")

            claimed = (await session.scalars(statement)).all()
            return set(claimed)

    async def mark_status(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
        status: DeliveryStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        async with self._session_factory.begin() as session:
            record = await session.scalar(
                select(DeliveryRecord).where(
                    DeliveryRecord.user_id == user_id,
                    DeliveryRecord.schedule_date == schedule_date,
                    DeliveryRecord.delivery_type == delivery_type.value,
                )
            )
            if record is None:
                raise LookupError("Yuborish rezervatsiyasi topilmadi")
            record.status = status.value
            record.error_code = error_code
            record.sent_at = datetime.now(UTC) if status is DeliveryStatus.SENT else None
            await session.flush()
