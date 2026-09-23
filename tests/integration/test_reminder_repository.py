import asyncio
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from namoz_bot.application.reminders import ReminderService
from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.domain.models import UserSubscription
from namoz_bot.domain.reminders import ReminderSpec
from namoz_bot.infrastructure.orm import Base, ReminderDeliveryRecord
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository


def migrate(connection, revision="head", downgrade=False):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = connection
    (command.downgrade if downgrade else command.upgrade)(config, revision)


@pytest.fixture(params=["sqlite", "postgres"])
async def session_factory(tmp_path, request):
    if request.param == "sqlite":
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reminders.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            yield async_sessionmaker(engine, expire_on_commit=False)
        finally:
            await engine.dispose()
        return
    url = os.getenv("NAMOZ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
    assert "test" in (make_url(url).database or "")
    schema = f"reminder_test_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as connection:
            await connection.run_sync(migrate)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


NOW = datetime(2026, 9, 23, 14, tzinfo=UTC)
DUE = datetime(2026, 9, 23, 15, tzinfo=UTC)


async def test_delete_is_owner_scoped_idempotent_and_cancels_delivery(session_factory):
    user = await add_user(session_factory)
    other = await add_user(session_factory, 8)
    repo = SqlAlchemyReminderRepository(session_factory)
    reminder = await repo.create(user, 7, ReminderSpec("Delete", time(20), "daily"), "del", NOW)
    assert await repo.get_for_user(other, reminder.id) is None
    assert await repo.delete_for_user(other, reminder.id) is False
    delivery = (await repo.claim_due(DUE, limit=10))[0]
    assert await repo.can_send(delivery) is True
    assert await repo.delete_for_user(user, reminder.id) is True
    assert await repo.delete_for_user(user, reminder.id) is False
    assert await repo.can_send(delivery) is False
    await repo.finish(delivery, "sent")  # A late completion cannot recreate the reminder.
    assert await repo.list_for_user(user, offset=0, limit=10) == []
    assert await repo.claim_due(datetime(2026, 9, 24, 15, tzinfo=UTC), limit=10) == []
    async with session_factory() as session:
        assert (await session.scalars(select(ReminderDeliveryRecord))).all() == []


async def add_user(factory, number=7):
    user = await SqlAlchemySubscriptionRepository(factory).add(
        UserSubscription(number, number, "Toshkent", True)
    )
    return user.id


async def test_date_list_includes_sent_occurrences_sorts_and_isolates_users(session_factory):
    user = await add_user(session_factory)
    other = await add_user(session_factory, 8)
    repo = SqlAlchemyReminderRepository(session_factory)
    specs = [
        ReminderSpec("Evening", time(22), "daily"),
        ReminderSpec("Tomorrow", time(7), "once", date(2026, 9, 24)),
        ReminderSpec("Wednesday", time(10), "weekly", weekdays=(0, 2, 4)),
        ReminderSpec("Sent today", time(8), "once", date(2026, 9, 23)),
        ReminderSpec("Tuesday", time(9), "weekly", weekdays=(1,)),
        ReminderSpec("Morning daily", time(6), "daily"),
        ReminderSpec("Yesterday", time(7), "once", date(2026, 9, 22)),
        ReminderSpec("Same time", time(10), "daily"),
    ]
    for i, spec in enumerate(specs):
        await repo.create(user, 7, spec, str(i), NOW - timedelta(days=3))
    await repo.create(other, 8, ReminderSpec("Private", time(5), "daily"), "other", NOW)
    for delivery in await repo.claim_due(NOW, limit=50):
        await repo.finish(delivery, "sent")
    rows = await repo.list_for_date(user, date(2026, 9, 23), offset=0, limit=3)
    assert [row.spec.text for row in rows] == ["Morning daily", "Sent today", "Wednesday"]
    rows = await repo.list_for_date(user, date(2026, 9, 23), offset=3, limit=3)
    assert [row.spec.text for row in rows] == ["Same time", "Evening"]
    assert await repo.list_for_date(user, date(2026, 9, 23), offset=5, limit=3) == []


async def test_concurrent_creation_is_idempotent_and_owner_scoped(session_factory):
    user = await add_user(session_factory)
    other = await add_user(session_factory, 8)
    repo = SqlAlchemyReminderRepository(session_factory)
    spec = ReminderSpec("Kitob", time(20), "daily")
    items = await asyncio.gather(*(repo.create(user, 7, spec, "token", NOW) for _ in range(2)))
    assert items[0].id == items[1].id
    assert items[0].next_due == DUE
    assert await repo.list_for_user(other, offset=0, limit=3) == []
    restored = await SqlAlchemyReminderRepository(session_factory).list_for_user(
        user, offset=0, limit=3
    )
    assert restored == [items[0]]


async def test_claim_is_atomic_and_once_is_never_reclaimed(session_factory):
    user = await add_user(session_factory)
    repo = SqlAlchemyReminderRepository(session_factory)
    spec = ReminderSpec("Meeting", time(20), "once", on_date=date(2026, 9, 23))
    await repo.create(user, 7, spec, "once", NOW)
    assert await repo.claim_due(NOW, limit=10) == []
    first, second = await asyncio.gather(
        repo.claim_due(DUE, limit=10), repo.claim_due(DUE, limit=10)
    )
    assert len(first + second) == 1
    await repo.finish((first + second)[0], "sent")
    assert await repo.claim_due(DUE, limit=10) == []
    assert (await repo.list_for_user(user, offset=0, limit=3))[0].status == "completed"


async def test_downtime_coalesces_and_pagination_orders_active_first(session_factory):
    user = await add_user(session_factory)
    repo = SqlAlchemyReminderRepository(session_factory)
    for i, kind in enumerate(["daily", "weekly", "once"]):
        spec = ReminderSpec(
            str(i),
            time(20),
            kind,
            weekdays=(2,) if kind == "weekly" else (),
            on_date=date(2026, 9, 23) if kind == "once" else None,
        )
        await repo.create(user, 7, spec, str(i), NOW)
    later = datetime(2026, 10, 7, 15, 1, tzinfo=UTC)
    claimed = await repo.claim_due(later, limit=10)
    assert len(claimed) == 3
    for delivery in claimed:
        await repo.finish(delivery, "sent")
    assert await repo.claim_due(later, limit=10) == []
    page = await repo.list_for_user(user, offset=0, limit=2)
    assert [r.spec.kind for r in page] == ["daily", "weekly"]
    assert page[0].next_due == datetime(2026, 10, 8, 15, tzinfo=UTC)
    assert page[1].next_due == datetime(2026, 10, 14, 15, tzinfo=UTC)
    assert (await repo.list_for_user(user, offset=2, limit=2))[0].status == "completed"


class CapturingSender:
    def __init__(self, blocked=None, failed=None):
        self.blocked = blocked
        self.failed = failed
        self.messages = []

    async def send(self, chat_id, text):
        if chat_id == self.blocked:
            raise RecipientBlockedError("blocked")
        if chat_id == self.failed:
            raise RuntimeError("network")
        self.messages.append((chat_id, text))


async def test_deleting_an_already_claimed_batch_item_prevents_send(session_factory):
    user = await add_user(session_factory)
    repo = SqlAlchemyReminderRepository(session_factory)
    await repo.create(user, 7, ReminderSpec("First", time(20), "daily"), "first", NOW)
    second = await repo.create(user, 7, ReminderSpec("Second", time(20), "daily"), "second", NOW)

    class DeleteWhileSending(CapturingSender):
        async def send(self, chat_id, text):
            await super().send(chat_id, text)
            await repo.delete_for_user(user, second.id)

    sender = DeleteWhileSending()
    await ReminderService(repo, now=lambda: DUE).send_due(sender)
    assert sender.messages == [(7, "🔔 Eslatma\n\nFirst")]


async def test_delete_can_race_claim_and_finish(session_factory):
    user = await add_user(session_factory)
    repo = SqlAlchemyReminderRepository(session_factory)
    reminder = await repo.create(
        user, 7, ReminderSpec("Concurrent", time(20), "daily"), "race", NOW
    )
    deliveries, deleted = await asyncio.gather(
        repo.claim_due(DUE, limit=10), repo.delete_for_user(user, reminder.id)
    )
    assert deleted
    for delivery in deliveries:
        assert not await repo.can_send(delivery)
    once = await repo.create(
        user, 7, ReminderSpec("Once", time(20), "once", on_date=date(2026, 9, 23)), "once-race", NOW
    )
    delivery = (await repo.claim_due(DUE, limit=10))[0]
    await asyncio.gather(repo.finish(delivery, "sent"), repo.delete_for_user(user, once.id))
    assert await repo.list_for_user(user, offset=0, limit=10) == []


async def test_deleted_delivery_cannot_target_a_new_reminder(session_factory):
    user = await add_user(session_factory)
    repo = SqlAlchemyReminderRepository(session_factory)
    spec = ReminderSpec("Old", time(20), "once", on_date=date(2026, 9, 23))
    old = await repo.create(user, 7, spec, "old", NOW)
    old_delivery = (await repo.claim_due(DUE, limit=10))[0]
    await repo.delete_for_user(user, old.id)
    new = await repo.create(user, 7, spec, "new", NOW)
    new_delivery = (await repo.claim_due(DUE, limit=10))[0]
    assert not await repo.can_send(old_delivery)
    await repo.finish(old_delivery, "sent")
    assert await repo.can_send(new_delivery)
    assert (await repo.get_for_user(user, new.id)).status == "processing"


async def test_worker_isolates_failure_pauses_blocked_and_survives_restart(session_factory):
    repo = SqlAlchemyReminderRepository(session_factory)
    for user_id in [7, 8, 9]:
        user = await add_user(session_factory, user_id)
        await repo.create(
            user, user_id, ReminderSpec("Hello <b>world</b>", time(20), "daily"), str(user_id), NOW
        )
    sender = CapturingSender(blocked=7, failed=8)
    service = ReminderService(repo, now=lambda: DUE)
    await service.send_due(sender)
    assert sender.messages == [(9, "🔔 Eslatma\n\nHello <b>world</b>")]
    await ReminderService(SqlAlchemyReminderRepository(session_factory), now=lambda: DUE).send_due(
        sender
    )
    assert len(sender.messages) == 1
    async with session_factory() as session:
        statuses = (await session.scalars(select(ReminderDeliveryRecord.status))).all()
    assert statuses.count("failed") == 2
    assert statuses.count("sent") == 1
    assert (await repo.list_for_user(1, offset=0, limit=3))[0].status == "paused"


async def test_migration_roundtrip_preserves_users(session_factory):
    async with session_factory() as session:
        if session.get_bind().dialect.name != "postgresql":
            pytest.skip("Alembic roundtrip is verified on PostgreSQL")
    await add_user(session_factory)
    async with session_factory.begin() as session:
        connection = await session.connection()
        await connection.run_sync(lambda c: migrate(c, "20260826_04", downgrade=True))
        tables = await connection.run_sync(lambda c: inspect(c).get_table_names())
        assert "users" in tables and "reminders" not in tables
        await connection.run_sync(migrate)
        assert await session.scalar(text("SELECT count(*) FROM users")) == 1
        assert await session.scalar(text("SELECT count(*) FROM reminders")) == 0


async def test_multiday_reminder_survives_restart_and_advances_between_selected_days(
    session_factory,
):
    user = await add_user(session_factory)
    repo = SqlAlchemyReminderRepository(session_factory)
    await repo.create(
        user, 7, ReminderSpec("Read", time(20), "weekly", weekdays=(0, 2, 4)), "days", NOW
    )
    sender = CapturingSender()
    await ReminderService(repo, now=lambda: DUE).send_due(sender)
    restarted = SqlAlchemyReminderRepository(session_factory)
    restored = (await restarted.list_for_user(user, offset=0, limit=3))[0]
    assert restored.spec.weekdays == (0, 2, 4)
    friday = datetime(2026, 9, 25, 15, tzinfo=UTC)
    assert restored.next_due == friday
    await ReminderService(restarted, now=lambda: friday).send_due(sender)
    await ReminderService(restarted, now=lambda: friday).send_due(sender)
    assert sender.messages == [(7, "🔔 Eslatma\n\nRead")] * 2
    assert (await restarted.list_for_user(user, offset=0, limit=3))[0].next_due == datetime(
        2026, 9, 28, 15, tzinfo=UTC
    )
    later = datetime(2026, 10, 7, 15, 1, tzinfo=UTC)
    await ReminderService(restarted, now=lambda: later).send_due(sender)
    assert len(sender.messages) == 3  # Missed occurrences are coalesced.
    assert (await restarted.list_for_user(user, offset=0, limit=3))[0].next_due == datetime(
        2026, 10, 9, 15, tzinfo=UTC
    )


async def test_weekday_migration_preserves_legacy_schedules_and_deliveries(session_factory):
    async with session_factory() as session:
        if session.get_bind().dialect.name != "postgresql":
            pytest.skip("Legacy Alembic data conversion is verified on PostgreSQL")
    user = await add_user(session_factory)
    async with session_factory.begin() as session:
        connection = await session.connection()
        await connection.run_sync(lambda c: migrate(c, "20260923_01", downgrade=True))
        for day in range(7):
            await session.execute(
                text(
                    "INSERT INTO reminders (user_id, chat_id, text, at, kind, weekday, next_due, "
                    "status, creation_token) VALUES (:user, 7, 'Legacy', '20:00', 'weekly', :day, "
                    ":due, 'active', :token)"
                ),
                {"user": user, "day": day, "due": DUE, "token": str(day)},
            )
        before = (
            await session.execute(
                text("SELECT id, user_id, next_due, status, weekday FROM reminders ORDER BY id")
            )
        ).all()
        await session.execute(
            text(
                "INSERT INTO reminder_deliveries (reminder_id, scheduled_at, status) "
                "VALUES (:id, :due, 'sent')"
            ),
            {"id": before[0].id, "due": NOW},
        )
        await connection.run_sync(migrate)
        after = (
            await session.execute(
                text(
                    "SELECT id, user_id, next_due, status, weekdays_mask FROM reminders ORDER BY id"
                )
            )
        ).all()
        assert [tuple(row[:4]) for row in before] == [tuple(row[:4]) for row in after]
        assert [row.weekdays_mask for row in after] == [1 << day for day in range(7)]
        assert await session.scalar(text("SELECT count(*) FROM reminder_deliveries")) == 1
        await connection.run_sync(lambda c: migrate(c, "20260923_01", downgrade=True))
        assert (
            await session.scalars(text("SELECT weekday FROM reminders ORDER BY id"))
        ).all() == list(range(7))
        await connection.run_sync(migrate)
    restored = await SqlAlchemyReminderRepository(session_factory).list_for_user(
        user, offset=0, limit=10
    )
    assert {row.spec.weekdays for row in restored} == {(day,) for day in range(7)}
    await SqlAlchemyReminderRepository(session_factory).create(
        user, 7, ReminderSpec("Multi", time(20), "weekly", weekdays=(0, 2)), "multi", NOW
    )
    with pytest.raises(RuntimeError, match="multi-day reminders"):
        async with session_factory.begin() as session:
            connection = await session.connection()
            await connection.run_sync(lambda c: migrate(c, "20260923_01", downgrade=True))
    assert (
        len(
            await SqlAlchemyReminderRepository(session_factory).list_for_user(
                user, offset=0, limit=10
            )
        )
        == 8
    )
