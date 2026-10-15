"""Durable reminder storage and atomic occurrence reservations."""

from dataclasses import asdict
from datetime import UTC, date, datetime

from sqlalchemy import and_, case, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.reminders import Reminder, ReminderDelivery, ReminderSpec, parse_time
from namoz_bot.domain.workforce.corrections import CorrectionConflict, ReminderCorrection
from namoz_bot.infrastructure.orm import ReminderDeliveryRecord, ReminderRecord
from namoz_bot.infrastructure.session_scope import session_scope
from namoz_bot.infrastructure.workforce.corrections import audit_correction, existing_correction


def _spec(row: ReminderRecord) -> ReminderSpec:
    days = tuple(day for day in range(7) if (row.weekdays_mask or 0) & (1 << day))
    return ReminderSpec(row.text, parse_time(row.at), row.kind, row.on_date, days)


def _entity(row: ReminderRecord) -> Reminder:
    due = row.next_due
    if due is not None and due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return Reminder(row.id, row.user_id, _spec(row), due, row.status, row.record_revision)


class SqlAlchemyReminderRepository:
    def __init__(
        self, factory: async_sessionmaker[AsyncSession], *, session: AsyncSession | None = None
    ) -> None:
        self._factory = factory
        self._session = session

    async def find_for_user(self, user_id: int, text: str) -> list[Reminder]:
        async with session_scope(self._factory, self._session, write=False) as session:
            rows = await session.scalars(
                select(ReminderRecord)
                .where(
                    ReminderRecord.user_id == user_id,
                    ReminderRecord.text.icontains(text, autoescape=True),
                )
                .order_by(ReminderRecord.id)
                .limit(20)
            )
            return [_entity(row) for row in rows]

    async def create(
        self, user_id: int, chat_id: int, spec: ReminderSpec, token: str, now: datetime
    ) -> Reminder:
        due = spec.next_after(now)
        async with session_scope(self._factory, self._session, write=True) as session:
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
        async with session_scope(self._factory, self._session, write=False) as session:
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

    async def list_for_date(
        self, user_id: int, on_date: date, *, offset: int, limit: int
    ) -> list[Reminder]:
        # Match the schedule, not next_due: sent occurrences still belong to this date.
        async with session_scope(self._factory, self._session, write=False) as session:
            rows = await session.scalars(
                select(ReminderRecord)
                .where(
                    ReminderRecord.user_id == user_id,
                    or_(
                        ReminderRecord.kind == "daily",
                        and_(ReminderRecord.kind == "once", ReminderRecord.on_date == on_date),
                        and_(
                            ReminderRecord.kind == "weekly",
                            ReminderRecord.weekdays_mask.bitwise_and(1 << on_date.weekday()) != 0,
                        ),
                    ),
                )
                .order_by(ReminderRecord.at, ReminderRecord.id)
                .offset(max(0, offset))
                .limit(limit)
            )
            return [_entity(row) for row in rows]

    async def claim_due(self, now: datetime, *, limit: int) -> list[ReminderDelivery]:
        claimed = []
        async with session_scope(self._factory, self._session, write=True) as session:
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
                delivery = ReminderDeliveryRecord(
                    reminder_id=row.id, scheduled_at=due, record_revision=row.record_revision
                )
                session.add(delivery)
                await session.flush()
                claimed.append(
                    ReminderDelivery(
                        delivery.id, row.id, row.user_id, row.chat_id, row.text, row.record_revision
                    )
                )
        return claimed

    async def get_for_user(self, user_id: int, reminder_id: int) -> Reminder | None:
        async with session_scope(self._factory, self._session, write=False) as session:
            row = await session.scalar(
                select(ReminderRecord).where(
                    ReminderRecord.id == reminder_id, ReminderRecord.user_id == user_id
                )
            )
            return _entity(row) if row is not None else None

    async def delete_for_user(self, user_id: int, reminder_id: int) -> bool:
        async with session_scope(self._factory, self._session, write=True) as session:
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
        async with session_scope(self._factory, self._session, write=False) as session:
            return (
                await session.scalar(
                    select(ReminderDeliveryRecord.id)
                    .join(ReminderRecord, ReminderRecord.id == ReminderDeliveryRecord.reminder_id)
                    .where(
                        ReminderDeliveryRecord.id == delivery.id,
                        ReminderRecord.id == delivery.reminder_id,
                        ReminderRecord.user_id == delivery.user_id,
                        ReminderDeliveryRecord.status == "pending",
                        ReminderRecord.record_revision == delivery.record_revision,
                        ReminderDeliveryRecord.record_revision == delivery.record_revision,
                    )
                )
                is not None
            )

    async def finish(
        self, delivery: ReminderDelivery, status: str, error: str | None = None
    ) -> None:
        async with session_scope(self._factory, self._session, write=True) as session:
            parent = await session.scalar(
                select(ReminderRecord)
                .where(ReminderRecord.id == delivery.reminder_id)
                .with_for_update()
            )
            occurrence = await session.get(ReminderDeliveryRecord, delivery.id)
            if (
                parent is None
                or occurrence is None
                or occurrence.status != "pending"
                or parent.record_revision != delivery.record_revision
                or occurrence.record_revision != delivery.record_revision
            ):
                return
            # Conditional updates also tolerate SQLite deleting the row after
            # the reads above (its SELECT FOR UPDATE does not acquire a lock).
            won = await session.scalar(
                update(ReminderDeliveryRecord)
                .where(
                    ReminderDeliveryRecord.id == delivery.id,
                    ReminderDeliveryRecord.reminder_id == delivery.reminder_id,
                    ReminderDeliveryRecord.status == "pending",
                    ReminderDeliveryRecord.record_revision == delivery.record_revision,
                )
                .values(status=status, error_code=error[:100] if error else None)
                .returning(ReminderDeliveryRecord.id)
                .execution_options(synchronize_session=False)
            )
            if won is not None:
                await session.execute(
                    update(ReminderRecord)
                    .where(
                        ReminderRecord.id == delivery.reminder_id,
                        ReminderRecord.record_revision == delivery.record_revision,
                        ReminderRecord.status == "processing",
                    )
                    .values(status="completed" if status == "sent" else "failed")
                    .execution_options(synchronize_session=False)
                )

    async def pause_user(self, user_id: int) -> None:
        async with session_scope(self._factory, self._session, write=True) as session:
            await session.execute(
                update(ReminderRecord)
                .where(
                    ReminderRecord.user_id == user_id,
                    ReminderRecord.status.in_(["active", "processing"]),
                )
                .values(status="paused")
            )

    async def update(
        self, user_id: int, correction: ReminderCorrection, source_key: str, now: datetime
    ) -> Reminder:
        spec = correction.replacement
        due = spec.next_after(now)
        async with session_scope(self._factory, self._session, write=True) as session:
            from namoz_bot.infrastructure.workforce.profiles import lock_owner

            await lock_owner(session, user_id)
            receipt = await existing_correction(
                session, user_id, source_key, "reminder", correction.original_reminder_id
            )
            row = await session.scalar(
                select(ReminderRecord)
                .where(
                    ReminderRecord.id == correction.original_reminder_id,
                    ReminderRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if row is None:
                raise CorrectionConflict("Original reminder missing")
            if receipt:
                return _entity(row)
            if row.record_revision != correction.expected_record_revision:
                raise CorrectionConflict("Reminder changed; confirm again")
            before = asdict(_entity(row))
            row.text, row.at, row.kind, row.on_date = (
                spec.text,
                spec.at.strftime("%H:%M"),
                spec.kind,
                spec.on_date,
            )
            row.weekdays_mask = sum(1 << day for day in spec.weekdays) or None
            row.next_due, row.status = due, "active"
            row.record_revision += 1
            await session.execute(
                update(ReminderDeliveryRecord)
                .where(
                    ReminderDeliveryRecord.reminder_id == row.id,
                    ReminderDeliveryRecord.status == "pending",
                )
                .values(status="superseded")
            )
            await session.flush()
            value = _entity(row)
            audit_correction(
                session,
                user_id=user_id,
                source_key=source_key,
                kind="reminder",
                original_id=row.id,
                replacement_id=row.id,
                before=before,
                after=asdict(value),
            )
            return value
