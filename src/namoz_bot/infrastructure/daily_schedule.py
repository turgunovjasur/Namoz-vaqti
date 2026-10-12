"""Durable daily send times and atomic per-user reservations."""

from datetime import UTC, datetime, time

from sqlalchemy import exists, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.daily_schedule import (
    DailySchedulePreference,
    DailyScheduleRecipient,
    next_daily_time,
)
from namoz_bot.domain.errors import SubscriptionNotFoundError
from namoz_bot.domain.reminders import parse_time
from namoz_bot.infrastructure.orm import DailyScheduleRecord, UserRecord
from namoz_bot.infrastructure.repositories import _to_subscription


def _preference(row: DailyScheduleRecord) -> DailySchedulePreference:
    due = row.next_due
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return DailySchedulePreference(row.user_id, parse_time(row.at), due)


class SqlAlchemyDailyScheduleRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def ensure_defaults(self, at: time, now: datetime) -> None:
        due = next_daily_time(at, now)
        async with self._factory.begin() as session:
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            missing = select(UserRecord.id, literal(at.strftime("%H:%M")), literal(due)).where(
                ~exists().where(DailyScheduleRecord.user_id == UserRecord.id)
            )
            await session.execute(
                insert(DailyScheduleRecord)
                .from_select(["user_id", "at", "next_due"], missing)
                .on_conflict_do_nothing(index_elements=["user_id"])
            )

    async def get(self, telegram_user_id: int) -> DailySchedulePreference:
        async with self._factory() as session:
            row = await session.scalar(
                select(DailyScheduleRecord)
                .join(UserRecord)
                .where(UserRecord.telegram_user_id == telegram_user_id)
            )
            if row is None:
                raise SubscriptionNotFoundError("Avval /start buyrug‘ini yuboring.")
            return _preference(row)

    async def set_time(
        self, telegram_user_id: int, at: time, now: datetime
    ) -> DailySchedulePreference:
        due = next_daily_time(at, now)
        async with self._factory.begin() as session:
            user_id = await session.scalar(
                select(UserRecord.id).where(UserRecord.telegram_user_id == telegram_user_id)
            )
            if user_id is None:
                raise SubscriptionNotFoundError("Avval /start buyrug‘ini yuboring.")
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(DailyScheduleRecord)
                .values(user_id=user_id, at=at.strftime("%H:%M"), next_due=due)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={"at": at.strftime("%H:%M"), "next_due": due},
                )
            )
            return DailySchedulePreference(user_id, at, due)

    async def list_due(self, now: datetime, *, limit: int) -> list[DailyScheduleRecipient]:
        async with self._factory() as session:
            rows = await session.execute(
                select(DailyScheduleRecord, UserRecord)
                .join(UserRecord)
                .where(UserRecord.is_active.is_(True), DailyScheduleRecord.next_due <= now)
                .order_by(DailyScheduleRecord.next_due, DailyScheduleRecord.user_id)
                .limit(limit)
            )
            return [
                DailyScheduleRecipient(_to_subscription(user), _preference(row))
                for row, user in rows
            ]

    async def claim(self, item: DailyScheduleRecipient, now: datetime) -> bool:
        preference = item.preference
        async with self._factory.begin() as session:
            won = await session.scalar(
                update(DailyScheduleRecord)
                .where(
                    DailyScheduleRecord.user_id == preference.user_id,
                    DailyScheduleRecord.at == preference.at.strftime("%H:%M"),
                    DailyScheduleRecord.next_due == preference.next_due,
                    exists().where(
                        UserRecord.id == preference.user_id, UserRecord.is_active.is_(True)
                    ),
                )
                .values(next_due=next_daily_time(preference.at, now))
                .returning(DailyScheduleRecord.user_id)
            )
            return won is not None
