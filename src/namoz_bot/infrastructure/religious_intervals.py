"""Persist user intervals and reserve due sends across restarts."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.errors import SubscriptionNotFoundError
from namoz_bot.domain.religious_intervals import ReligiousInterval, next_interval_time
from namoz_bot.infrastructure.orm import ReligiousIntervalRecord, UserRecord


def _entity(row: ReligiousIntervalRecord, user: UserRecord) -> ReligiousInterval:
    due = row.next_due
    if due is not None and due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return ReligiousInterval(user.id, user.telegram_user_id, user.chat_id, row.interval_hours, due)


class SqlAlchemyReligiousIntervalRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def ensure_defaults(self, hours: float, now: datetime) -> None:
        due = next_interval_time(now, hours)
        async with self._factory.begin() as session:
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            missing = select(UserRecord.id, literal(hours), literal(due)).where(
                ~exists().where(ReligiousIntervalRecord.user_id == UserRecord.id)
            )
            await session.execute(
                insert(ReligiousIntervalRecord)
                .from_select(["user_id", "interval_hours", "next_due"], missing)
                .on_conflict_do_nothing(index_elements=["user_id"])
            )

    async def get(self, telegram_user_id: int) -> ReligiousInterval:
        async with self._factory() as session:
            result = (
                await session.execute(
                    select(ReligiousIntervalRecord, UserRecord)
                    .join(UserRecord)
                    .where(UserRecord.telegram_user_id == telegram_user_id)
                )
            ).first()
            if result is None:
                raise SubscriptionNotFoundError("Avval /start buyrug‘ini yuboring.")
            return _entity(result[0], result[1])

    async def set_interval(
        self, telegram_user_id: int, hours: float, now: datetime
    ) -> ReligiousInterval:
        due = next_interval_time(now, hours)
        async with self._factory.begin() as session:
            user = await session.scalar(
                select(UserRecord).where(UserRecord.telegram_user_id == telegram_user_id)
            )
            if user is None:
                raise SubscriptionNotFoundError("Avval /start buyrug‘ini yuboring.")
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(ReligiousIntervalRecord)
                .values(user_id=user.id, interval_hours=hours, next_due=due)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={"interval_hours": hours, "next_due": due},
                )
            )
            return ReligiousInterval(user.id, user.telegram_user_id, user.chat_id, hours, due)

    async def list_due(self, now: datetime, *, limit: int) -> list[ReligiousInterval]:
        async with self._factory() as session:
            rows = await session.execute(
                select(ReligiousIntervalRecord, UserRecord)
                .join(UserRecord)
                .where(
                    UserRecord.is_active.is_(True),
                    ReligiousIntervalRecord.interval_hours > 0,
                    ReligiousIntervalRecord.next_due <= now,
                )
                .order_by(ReligiousIntervalRecord.next_due, ReligiousIntervalRecord.user_id)
                .limit(limit)
            )
            return [_entity(row, user) for row, user in rows]

    async def claim(self, item: ReligiousInterval, now: datetime) -> bool:
        if item.next_due is None or item.interval_hours <= 0:
            return False
        interval = timedelta(hours=item.interval_hours)
        next_due = item.next_due + ((now - item.next_due) // interval + 1) * interval
        async with self._factory.begin() as session:
            won = await session.scalar(
                update(ReligiousIntervalRecord)
                .where(
                    ReligiousIntervalRecord.user_id == item.user_id,
                    ReligiousIntervalRecord.interval_hours == item.interval_hours,
                    ReligiousIntervalRecord.next_due == item.next_due,
                    exists().where(UserRecord.id == item.user_id, UserRecord.is_active.is_(True)),
                )
                .values(next_due=next_due)
                .returning(ReligiousIntervalRecord.user_id)
            )
            return won is not None
