import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from namoz_bot.domain.models import UserSubscription
from namoz_bot.infrastructure.orm import Base
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository

NOW = datetime(2026, 10, 9, 7, tzinfo=UTC)


@pytest.fixture(params=["sqlite", "postgres"])
async def interval_store(tmp_path, request):
    admin = None
    schema = f"interval_test_{uuid4().hex}"
    if request.param == "postgres":
        url = os.getenv("NAMOZ_TEST_DATABASE_URL")
        if url is None:
            pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
        from tests.integration.test_reminder_repository import migrate

        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        async with engine.begin() as connection:
            await connection.run_sync(migrate)
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'intervals.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        users = SqlAlchemySubscriptionRepository(factory)
        for identifier in (7, 8):
            await users.add(UserSubscription(identifier, identifier, "Toshkent", True))
        yield factory, users
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


def repository(factory):
    # Import lazily so missing implementation is reported as a test failure.
    import namoz_bot.infrastructure.religious_intervals as module

    return module.SqlAlchemyReligiousIntervalRepository(factory)


async def test_default_daily_interval_and_personal_choice_survive_repository_restart(
    interval_store,
):
    factory, users = interval_store
    repo = repository(factory)
    await repo.ensure_defaults(24, NOW)
    assert (await repo.get(7)).next_due == NOW + timedelta(hours=24)
    chosen = await repo.set_interval(7, 6, NOW)
    await users.upsert_start(UserSubscription(7, 7, "Toshkent", True))
    restored = repository(factory)
    await restored.ensure_defaults(24, NOW + timedelta(hours=1))
    assert await restored.get(7) == chosen
    assert (await restored.get(8)).interval_hours == 24
    assert [
        p.telegram_user_id for p in await restored.list_due(NOW + timedelta(hours=6), limit=10)
    ] == [7]


async def test_claim_is_atomic_and_overdue_intervals_coalesce_into_one(interval_store):
    factory, _ = interval_store
    repo = repository(factory)
    await repo.ensure_defaults(24, NOW)
    await repo.set_interval(7, 2, NOW)
    overdue = NOW + timedelta(days=1, minutes=30)
    item = next(p for p in await repo.list_due(overdue, limit=10) if p.telegram_user_id == 7)
    claims = await asyncio.gather(
        repo.claim(item, overdue), repository(factory).claim(item, overdue)
    )
    assert sorted(claims) == [False, True]
    assert (await repo.get(7)).next_due == NOW + timedelta(hours=26)


async def test_disable_or_interval_change_invalidates_pending_claim_and_keeps_prayer_subscription(
    interval_store,
):
    factory, users = interval_store
    repo = repository(factory)
    await repo.ensure_defaults(24, NOW)
    item = (await repo.list_due(NOW + timedelta(days=1), limit=10))[0]
    await repo.set_interval(item.telegram_user_id, 0, NOW)
    assert await repo.claim(item, NOW + timedelta(days=1)) is False
    assert (await repo.get(item.telegram_user_id)).next_due is None
    assert (await users.get_by_telegram_user_id(item.telegram_user_id)).is_active is True
    await repo.set_interval(item.telegram_user_id, 6, NOW + timedelta(days=1))
    assert await repo.claim(item, NOW + timedelta(days=1)) is False


@pytest.mark.parametrize("hours", [-1, 169, float("nan"), float("inf"), True])
async def test_invalid_interval_does_not_change_saved_choice(interval_store, hours):
    factory, _ = interval_store
    repo = repository(factory)
    await repo.ensure_defaults(24, NOW)
    before = await repo.get(7)
    with pytest.raises(ValueError):
        await repo.set_interval(7, hours, NOW)
    assert await repo.get(7) == before


async def test_personal_broadcast_sends_only_due_users_and_does_not_replay_after_restart(
    interval_store,
):
    from namoz_bot.application.religious_reminders import PersonalReligiousBroadcastService
    from tests.unit.application.test_religious_broadcasting import ReligiousProvider, Sender

    factory, users = interval_store
    repo = repository(factory)
    await repo.ensure_defaults(24, NOW)
    await repo.set_interval(7, 6, NOW)
    provider, sender = ReligiousProvider(), Sender()
    broadcaster = PersonalReligiousBroadcastService(
        repo, users, provider, sender, clock=lambda: NOW + timedelta(hours=6)
    )
    report = await broadcaster.send()
    assert report.sent == 1
    assert [chat for chat, _ in sender.messages] == [7]
    restarted = PersonalReligiousBroadcastService(
        repository(factory), users, provider, sender, clock=lambda: NOW + timedelta(hours=6)
    )
    assert (await restarted.send()).sent == 0
    assert provider.calls == 1


async def test_gemini_failure_leaves_due_users_available_for_retry(interval_store):
    from namoz_bot.application.religious_reminders import PersonalReligiousBroadcastService
    from namoz_bot.domain.errors import ExternalServiceError
    from tests.unit.application.test_religious_broadcasting import ReligiousProvider, Sender

    factory, users = interval_store
    repo = repository(factory)
    await repo.ensure_defaults(24, NOW)
    provider = ReligiousProvider(fail=True)
    broadcaster = PersonalReligiousBroadcastService(
        repo, users, provider, Sender(), clock=lambda: NOW + timedelta(hours=24)
    )
    with pytest.raises(ExternalServiceError):
        await broadcaster.send()
    assert len(await repo.list_due(NOW + timedelta(hours=24), limit=10)) == 2


async def test_saved_interval_and_default_due_times_are_aligned_to_full_hours(interval_store):
    factory, _ = interval_store
    repo = repository(factory)
    now = NOW + timedelta(minutes=40, seconds=17)
    await repo.ensure_defaults(24, now)
    assert (await repo.get(8)).next_due == datetime(2026, 10, 10, 7, tzinfo=UTC)
    chosen = await repo.set_interval(7, 6, now)
    assert chosen.next_due == datetime(2026, 10, 9, 13, tzinfo=UTC)
    assert await repo.claim(chosen, datetime(2026, 10, 9, 13, 0, 30, tzinfo=UTC))
    assert (await repo.get(7)).next_due == datetime(2026, 10, 9, 19, tzinfo=UTC)


async def test_alignment_migration_preserves_disabled_choice_and_aligns_legacy_values(
    interval_store,
):
    from tests.integration.test_reminder_repository import migrate

    factory, users = interval_store
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Production migrations target PostgreSQL")
    active_user = await users.get_by_telegram_user_id(7)
    disabled_user = await users.get_by_telegram_user_id(8)
    async with factory.kw["bind"].begin() as connection:
        await connection.run_sync(lambda conn: migrate(conn, "20261009_01", downgrade=True))
        await connection.execute(
            text(
                "INSERT INTO religious_intervals (user_id, interval_hours, next_due) "
                "VALUES (:user_id, :hours, :due)"
            ),
            [
                {
                    "user_id": active_user.id,
                    "hours": 1.5,
                    "due": datetime(2026, 10, 9, 13, 40, 17, tzinfo=UTC),
                },
                {"user_id": disabled_user.id, "hours": 0, "due": None},
            ],
        )
        await connection.run_sync(migrate)
    active = await repository(factory).get(7)
    disabled = await repository(factory).get(8)
    assert active.interval_hours == 2
    assert active.next_due == datetime(2026, 10, 9, 13, tzinfo=UTC)
    assert disabled.interval_hours == 0
    assert disabled.next_due is None
