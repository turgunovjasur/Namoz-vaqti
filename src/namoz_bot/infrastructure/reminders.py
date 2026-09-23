"""Durable reminder storage and atomic occurrence reservations."""

from datetime import UTC, datetime

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.reminders import Reminder, ReminderDelivery, ReminderSpec, parse_time
from namoz_bot.infrastructure.orm import ReminderDeliveryRecord, ReminderRecord


def _spec(row: ReminderRecord) -> ReminderSpec:
    days = tuple(day for day in range(7) if (row.weekdays_mask or 0) & (1 << day))
    return ReminderSpec(row.text, parse_time(row.at), row.kind, row.on_date, days)


def _entity(row: ReminderRecord) -> Reminder:
    due = row.next_due
    if due is not None and due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return Reminder(row.id, row.user_id, _spec(row), due, row.status)


class SqlAlchemyReminderRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def create(
        self, user_id: int, chat_id: int, spec: ReminderSpec, token: str, now: datetime
    ) -> Reminder:
        due = spec.next_after(now)
        async with self._factory.begin() as session:
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(ReminderRecord)
                .values(
                    user_id=user_id,
                    chat_id=chat_id,
                    text=spec.text,
                    at=spec.at.strftime("%H:%M"),
                    kind=spec.kind,
                    on_date=spec.on_date,
                    weekdays_mask=sum(1 << day for day in spec.weekdays) or None,
                    next_due=due,
                    status="active",
                    creation_token=token,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "creation_token"])
            )
            row = await session.scalar(
                select(ReminderRecord).where(
                    ReminderRecord.user_id == user_id, ReminderRecord.creation_token == token
                )
            )
            assert row is not None
            return _entity(row)

    async def list_for_user(self, user_id: int, *, offset: int, limit: int) -> list[Reminder]:
        async with self._factory() as session:
            rows = await session.scalars(
                select(ReminderRecord)
                .where(ReminderRecord.user_id == user_id)
                .order_by(
                    case((ReminderRecord.status == "active", 0), else_=1),
                    ReminderRecord.next_due,
                    ReminderRecord.id,
                )
                .offset(max(0, offset))
                .limit(limit)
            )
            return [_entity(row) for row in rows]

    async def claim_due(self, now: datetime, *, limit: int) -> list[ReminderDelivery]:
        claimed = []
        async with self._factory.begin() as session:
            rows = (
                await session.scalars(
                    select(ReminderRecord)
                    .where(
                        ReminderRecord.status == "active",
                        ReminderRecord.next_due <= now,
                    )
                    .order_by(ReminderRecord.next_due, ReminderRecord.id)
                    .limit(limit)
                )
            ).all()
            for row in rows:
                due = row.next_due
                next_due = None if row.kind == "once" else _spec(row).next_after(now)
                won = await session.scalar(
                    update(ReminderRecord)
                    .where(
                        ReminderRecord.id == row.id,
                        ReminderRecord.status == "active",
                        ReminderRecord.next_due == due,
                    )
                    .values(
                        next_due=next_due, status="processing" if row.kind == "once" else "active"
                    )
                    .returning(ReminderRecord.id)
                    .execution_options(synchronize_session=False)
                )
                if won is None:
                    continue
                delivery = ReminderDeliveryRecord(reminder_id=row.id, scheduled_at=due)
                session.add(delivery)
                await session.flush()
                claimed.append(
                    ReminderDelivery(delivery.id, row.id, row.user_id, row.chat_id, row.text)
                )
        return claimed

    async def get_for_user(self, user_id: int, reminder_id: int) -> Reminder | None:
        async with self._factory() as session:
            row = await session.scalar(
                select(ReminderRecord).where(
                    ReminderRecord.id == reminder_id, ReminderRecord.user_id == user_id
                )
            )
            return _entity(row) if row is not None else None

    async def delete_for_user(self, user_id: int, reminder_id: int) -> bool:
        async with self._factory.begin() as session:
            # Serialize against claim_due's row update before removing its ledger.
            owned = await session.scalar(
                select(ReminderRecord.id)
                .where(ReminderRecord.id == reminder_id, ReminderRecord.user_id == user_id)
                .with_for_update()
            )
            if owned is None:
                return False
            await session.execute(
                delete(ReminderDeliveryRecord).where(
                    ReminderDeliveryRecord.reminder_id == reminder_id
                )
            )
            await session.execute(
                delete(ReminderRecord).where(
                    ReminderRecord.id == reminder_id, ReminderRecord.user_id == user_id
                )
            )
            return True

    async def can_send(self, delivery: ReminderDelivery) -> bool:
        async with self._factory() as session:
            return (
                await session.scalar(
                    select(ReminderDeliveryRecord.id)
                    .join(ReminderRecord, ReminderRecord.id == ReminderDeliveryRecord.reminder_id)
                    .where(
                        ReminderDeliveryRecord.id == delivery.id,
                        ReminderRecord.id == delivery.reminder_id,
                        ReminderRecord.user_id == delivery.user_id,
                        ReminderDeliveryRecord.status == "pending",
                    )
                )
                is not None
            )

    async def finish(
        self, delivery: ReminderDelivery, status: str, error: str | None = None
    ) -> None:
        async with self._factory.begin() as session:
            # Use the same parent-before-ledger lock order as delete_for_user.
            await session.execute(
                update(ReminderRecord)
                .where(
                    ReminderRecord.id == delivery.reminder_id,
                    ReminderRecord.status == "processing",
                )
                .values(status="completed" if status == "sent" else "failed")
            )
            await session.execute(
                update(ReminderDeliveryRecord)
                .where(ReminderDeliveryRecord.id == delivery.id)
                .values(status=status, error_code=error[:100] if error else None)
            )

    async def pause_user(self, user_id: int) -> None:
        async with self._factory.begin() as session:
            await session.execute(
                update(ReminderRecord)
                .where(
                    ReminderRecord.user_id == user_id,
                    ReminderRecord.status.in_(["active", "processing"]),
                )
                .values(status="paused")
            )
