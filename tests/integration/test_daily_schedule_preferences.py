from datetime import UTC, datetime, time

from tests.integration.test_religious_intervals import interval_store as _store_fixture

interval_store = _store_fixture
NOW = datetime(2026, 10, 9, 10, 40, tzinfo=UTC)


async def test_default_daily_time_and_changed_user_time_are_durable(interval_store):
    import namoz_bot.infrastructure.daily_schedule as module

    factory, users = interval_store
    repo = module.SqlAlchemyDailyScheduleRepository(factory)
    await repo.ensure_defaults(time(21), NOW)
    assert (await repo.get(8)).next_due == datetime(2026, 10, 9, 16, tzinfo=UTC)
    saved = await repo.set_time(7, time(18, 30), NOW)
    assert saved.at == time(18, 30)
    assert saved.next_due == datetime(2026, 10, 9, 13, 30, tzinfo=UTC)
    await users.upsert_start(await users.get_by_telegram_user_id(7))
    restarted = module.SqlAlchemyDailyScheduleRepository(factory)
    await restarted.ensure_defaults(time(21), datetime(2026, 10, 9, 11, tzinfo=UTC))
    assert await restarted.get(7) == saved
    assert (await restarted.get(8)).at == time(21)


async def test_daily_due_claim_is_once_and_setting_change_invalidates_old_candidate(interval_store):
    import namoz_bot.infrastructure.daily_schedule as module

    factory, _ = interval_store
    repo = module.SqlAlchemyDailyScheduleRepository(factory)
    await repo.ensure_defaults(time(21), NOW)
    candidates = await repo.list_due(datetime(2026, 10, 9, 16, tzinfo=UTC), limit=10)
    await repo.set_time(7, time(22), datetime(2026, 10, 9, 16, tzinfo=UTC))
    assert await repo.claim(candidates[0], datetime(2026, 10, 9, 16, tzinfo=UTC)) is False
    other = candidates[1]
    assert await repo.claim(other, datetime(2026, 10, 9, 16, tzinfo=UTC)) is True
    assert await repo.claim(other, datetime(2026, 10, 9, 16, tzinfo=UTC)) is False
    assert (await repo.get(8)).next_due == datetime(2026, 10, 10, 16, tzinfo=UTC)


async def test_daily_broadcast_only_reaches_due_user_with_tomorrow_schedule_once(interval_store):
    from namoz_bot.application.daily_schedule import PersonalDailyBroadcastService
    from namoz_bot.application.schedules import ScheduleService
    from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
    from tests.unit.application.test_broadcasting import Deliveries, Provider, Sender

    factory, users = interval_store
    repo = SqlAlchemyDailyScheduleRepository(factory)
    await repo.ensure_defaults(time(21), NOW)
    await repo.set_time(7, time(18, 30), NOW)
    provider, sender = Provider(), Sender()
    broadcast = PersonalDailyBroadcastService(
        repo,
        users,
        Deliveries(),
        ScheduleService(provider),
        sender,
        clock=lambda: datetime(2026, 10, 9, 13, 30, tzinfo=UTC),
    )
    assert (await broadcast.send()).sent == 1
    assert [chat for chat, _ in sender.messages] == [7]
    assert provider.calls == [("Toshkent", datetime(2026, 10, 10).date())]
    assert (await broadcast.send()).sent == 0


async def test_missed_days_send_latest_tomorrow_once_even_after_same_day_time_change(
    interval_store,
):
    from namoz_bot.application.daily_schedule import PersonalDailyBroadcastService
    from namoz_bot.application.schedules import ScheduleService
    from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
    from namoz_bot.infrastructure.repositories import SqlAlchemyDeliveryRepository
    from tests.unit.application.test_broadcasting import Provider, Sender

    factory, users = interval_store
    repo = SqlAlchemyDailyScheduleRepository(factory)
    await repo.ensure_defaults(time(21), NOW)
    provider, sender = Provider(), Sender()
    current = datetime(2026, 10, 12, 16, tzinfo=UTC)
    broadcast = PersonalDailyBroadcastService(
        repo,
        users,
        SqlAlchemyDeliveryRepository(factory),
        ScheduleService(provider),
        sender,
        clock=lambda: current,
    )
    assert (await broadcast.send()).sent == 2
    assert provider.calls == [("Toshkent", datetime(2026, 10, 13).date())]
    assert (await repo.get(7)).next_due == datetime(2026, 10, 13, 16, tzinfo=UTC)
    await repo.set_time(7, time(22), current)
    current = datetime(2026, 10, 12, 17, tzinfo=UTC)
    report = await broadcast.send()
    assert report.sent == 0
    assert report.skipped == 1
    assert [chat for chat, _ in sender.messages] == [7, 8]
