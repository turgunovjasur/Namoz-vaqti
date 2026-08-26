from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

import namoz_bot.presentation.handlers as handlers_module
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.models import PrayerSchedule, PrayerTimes, UserSubscription
from namoz_bot.presentation.handlers import (
    HandlerServices,
    handle_region_selection,
    handle_settings,
    handle_start,
    handle_toggle_notifications,
)


class InMemorySubscriptions:
    def __init__(self, existing: UserSubscription | None = None) -> None:
        self.item = existing

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None:
        if self.item is not None and self.item.telegram_user_id == telegram_user_id:
            return self.item
        return None

    async def add(self, subscription: UserSubscription) -> UserSubscription:
        self.item = UserSubscription(
            id=1,
            telegram_user_id=subscription.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=subscription.region_code,
            is_active=subscription.is_active,
        )
        return self.item

    async def upsert_start(self, subscription: UserSubscription) -> tuple[UserSubscription, bool]:
        if self.item is None:
            return await self.add(subscription), True
        self.item = UserSubscription(
            telegram_user_id=self.item.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=self.item.region_code,
            is_active=True,
            id=self.item.id,
        )
        return self.item, False

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self.item = subscription
        return subscription

    async def list_active_page(self, *, after_id: int, limit: int) -> list[UserSubscription]:
        del after_id, limit
        return [] if self.item is None or not self.item.is_active else [self.item]


class ScheduleProvider:
    async def get_today(self, region_code: str) -> PrayerSchedule:
        return await self.get_for_date(region_code, date(2026, 8, 27))

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        display_name = "Samarqand" if region_code == "Samarqand" else "Toshkent"
        return PrayerSchedule(
            date=target_date,
            region_code=region_code,
            region_name=display_name,
            times=PrayerTimes("04:17", "05:42", "12:25", "17:10", "19:12", "20:32"),
        )


@dataclass
class Answer:
    text: str
    kwargs: dict[str, Any]


class FakeMessage:
    def __init__(self, user_id: int = 7, chat_id: int = 9) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self.answers: list[Answer] = []

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append(Answer(text, kwargs))


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage, user_id: int = 7) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=user_id)
        self.answered = False
        self.answer_text: str | None = None

    async def answer(self, text: str | None = None, **_kwargs: Any) -> None:
        self.answered = True
        self.answer_text = text


def make_services(repository: InMemorySubscriptions) -> HandlerServices:
    return HandlerServices(
        subscriptions=SubscriptionService(repository),
        schedules=ScheduleService(ScheduleProvider()),
        today=lambda: date(2026, 8, 27),
    )


async def test_start_uses_saved_region_and_shared_schedule_format() -> None:
    repository = InMemorySubscriptions(UserSubscription(7, 8, "Samarqand", False, id=1))
    message = FakeMessage()

    await handle_start(message, make_services(repository))

    assert "📅 Bugun — 27-avgust, Samarqand" in message.answers[0].text
    assert repository.item is not None
    assert repository.item.chat_id == 9
    assert repository.item.is_active is True


async def test_region_selection_persists_region_and_sends_today_schedule() -> None:
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    message = FakeMessage()
    callback = FakeCallback(data="region:Samarqand", message=message)

    await handle_region_selection(callback, make_services(repository))

    assert callback.answered is True
    assert repository.item is not None
    assert repository.item.region_code == "Samarqand"
    assert "Samarqand" in message.answers[0].text


async def test_stale_region_button_requests_settings_refresh() -> None:
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    callback = FakeCallback(data="region:0:34", message=FakeMessage())

    await handle_region_selection(callback, make_services(repository))

    assert callback.answer_text == "Menyu yangilangan. /settings ni qayta oching"


async def test_settings_starts_with_geographic_groups() -> None:
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    message = FakeMessage()

    await handle_settings(message, make_services(repository))

    buttons = [
        button
        for row in message.answers[0].kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert len(buttons) == 14
    assert buttons[0].callback_data == "region-group:toshkent-shahri"


async def test_group_selection_shows_only_that_groups_locations() -> None:
    handler = getattr(handlers_module, "handle_region_group_selection", None)
    message = FakeMessage()
    callback = FakeCallback(data="region-group:andijon-viloyati", message=message)

    assert handler is not None
    await handler(callback)

    buttons = [
        button
        for row in message.answers[0].kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert callback.answered is True
    assert buttons[0].text == "Andijon viloyati"
    assert buttons[-1].callback_data == "region-groups"


async def test_back_to_groups_shows_top_level_selector() -> None:
    handler = getattr(handlers_module, "handle_region_groups", None)
    message = FakeMessage()
    callback = FakeCallback(data="region-groups", message=message)

    assert handler is not None
    await handler(callback)

    buttons = [
        button
        for row in message.answers[0].kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert callback.answered is True
    assert len(buttons) == 14
    assert buttons[0].callback_data == "region-group:toshkent-shahri"


async def test_toggle_notifications_updates_state_and_menu() -> None:
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    message = FakeMessage()

    await handle_toggle_notifications(message, make_services(repository))

    assert repository.item is not None
    assert repository.item.is_active is False
    labels = [
        button.text for row in message.answers[0].kwargs["reply_markup"].keyboard for button in row
    ]
    assert "🔔 Xabarlarni yoqish" in labels
