from datetime import time, timedelta

import pytest

from namoz_bot.application.daily_schedule import PersonalDailyBroadcastService
from namoz_bot.application.religious_reminders import PersonalReligiousBroadcastService
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.domain.reminders import ReminderSpec
from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
from namoz_bot.infrastructure.religious_intervals import SqlAlchemyReligiousIntervalRepository
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)
from tests.acceptance.harness import FakeScheduleProvider
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant
from tests.unit.application.test_broadcasting import Sender


class Book:
    async def generate(self):
        return "Asl kitob parchasi"


@pytest.mark.parametrize("kind", ["daily", "nasihat", "reminder"])
async def test_disabled_deliveries_advance_without_backlog_and_resume_future(
    access_setup, store, kind
):
    profiles, access, user, _ = access_setup
    _, factory, _, _ = store
    sender = Sender()
    users = SqlAlchemySubscriptionRepository(factory)
    current = NOW + timedelta(days=2)
    if kind == "daily":
        role, cap = "settings", "settings.deliver_daily"
        repo = SqlAlchemyDailyScheduleRepository(factory)
        await repo.ensure_defaults(time(15), NOW)
        service = PersonalDailyBroadcastService(
            repo,
            users,
            SqlAlchemyDeliveryRepository(factory),
            ScheduleService(FakeScheduleProvider()),
            sender,
            clock=lambda: current,
            access=access,
        )
    elif kind == "nasihat":
        role, cap = "nasihat", "nasihat.deliver"
        repo = SqlAlchemyReligiousIntervalRepository(factory)
        await repo.ensure_defaults(1, NOW)
        service = PersonalReligiousBroadcastService(
            repo, users, Book(), sender, clock=lambda: current, access=access
        )
    else:
        role, cap = "reminder", "reminder.deliver"
        repo = SqlAlchemyReminderRepository(factory)
        await repo.create(user, 7, ReminderSpec("Kitob", time(16), "daily"), "old", NOW)
        service = ReminderService(repo, now=lambda: current, access=access)

    async def send():
        if kind == "reminder":
            await service.send_due(sender)
        else:
            await service.send()

    await send()
    assert not sender.messages
    await grant(profiles, user, user, role, {cap})
    await send()
    assert not sender.messages
    current += timedelta(days=1)
    await send()
    assert len(sender.messages) == 1 and sender.messages[0][0] == 7
