import asyncio
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

import namoz_bot.presentation.handlers as handlers_module
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.models import (
    OffsetAction,
    PrayerKey,
    PrayerOffsets,
    PrayerSchedule,
    PrayerTimes,
    UserSubscription,
)
from namoz_bot.presentation.handlers import (
    HandlerServices,
    handle_region_selection,
    handle_settings,
    handle_start,
    handle_today,
    handle_toggle_notifications,
)


class InMemorySubscriptions:
    def __init__(
        self,
        existing: UserSubscription | None = None,
        *,
        fail_save: bool = False,
    ) -> None:
        self.item = existing
        self.fail_save = fail_save
        self.save_calls = 0

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
            offsets=subscription.offsets,
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
            offsets=self.item.offsets,
        )
        return self.item, False

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self.save_calls += 1
        if self.fail_save:
            raise RuntimeError("database unavailable")
        self.item = subscription
        return subscription

    async def change_offset(
        self,
        telegram_user_id: int,
        prayer: PrayerKey,
        action: OffsetAction,
    ) -> UserSubscription:
        assert self.item is not None and self.item.telegram_user_id == telegram_user_id
        offsets = self.item.offsets.change(prayer, action)
        return await self.save(self.item.with_preferences(offsets=offsets))

    async def change_region(
        self,
        telegram_user_id: int,
        region_code: str,
    ) -> UserSubscription:
        assert self.item is not None and self.item.telegram_user_id == telegram_user_id
        return await self.save(
            self.item.with_preferences(region_code=region_code, offsets=PrayerOffsets())
        )

    async def set_active(
        self,
        telegram_user_id: int,
        active: bool,
    ) -> UserSubscription:
        assert self.item is not None and self.item.telegram_user_id == telegram_user_id
        return await self.save(self.item.with_preferences(is_active=active))

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
        self.edits: list[Answer] = []

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append(Answer(text, kwargs))

    async def edit_text(self, text: str, **kwargs: Any) -> None:
        self.edits.append(Answer(text, kwargs))


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage | None, user_id: int = 7) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=user_id)
        self.answered = False
        self.answer_text: str | None = None
        self.answer_kwargs: dict[str, Any] = {}

    async def answer(self, text: str | None = None, **kwargs: Any) -> None:
        self.answered = True
        self.answer_text = text
        self.answer_kwargs = kwargs


def make_services(
    repository: InMemorySubscriptions,
    provider: ScheduleProvider | None = None,
) -> HandlerServices:
    return HandlerServices(
        subscriptions=SubscriptionService(repository),
        schedules=ScheduleService(provider or ScheduleProvider()),
        today=lambda: date(2026, 8, 27),
    )


async def test_start_uses_saved_region_and_shared_schedule_format() -> None:
    repository = InMemorySubscriptions(
        UserSubscription(
            7,
            8,
            "Samarqand",
            False,
            id=1,
            offsets=PrayerOffsets(shom=4),
        )
    )
    message = FakeMessage()

    await handle_start(message, make_services(repository))

    assert "📅 Bugun — 27-avgust, Samarqand" in message.answers[0].text
    assert "Shom — 19:16 (+4 daqiqa)" in message.answers[0].text
    assert repository.item is not None
    assert repository.item.chat_id == 9
    assert repository.item.is_active is True


async def test_today_applies_saved_prayer_offsets() -> None:
    repository = InMemorySubscriptions(
        UserSubscription(7, 9, "Toshkent", True, id=1, offsets=PrayerOffsets(shom=4))
    )
    message = FakeMessage()

    await handle_today(message, make_services(repository))

    assert "Shom — 19:16 (+4 daqiqa)" in message.answers[0].text


async def test_region_selection_persists_region_and_sends_today_schedule() -> None:
    repository = InMemorySubscriptions(
        UserSubscription(
            7,
            9,
            "Toshkent",
            True,
            id=1,
            offsets=PrayerOffsets(shom=4),
        )
    )
    message = FakeMessage()
    callback = FakeCallback(data="region:Samarqand", message=message)

    await handle_region_selection(callback, make_services(repository))

    assert callback.answered is True
    assert repository.item is not None
    assert repository.item.region_code == "Samarqand"
    assert repository.item.offsets == PrayerOffsets()
    assert message.answers == []
    assert len(message.edits) == 1
    assert "Samarqand" in message.edits[0].text
    assert "(+4 daqiqa)" not in message.edits[0].text


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

    assert message.answers == []
    assert len(message.edits) == 1
    buttons = [
        button for row in message.edits[0].kwargs["reply_markup"].inline_keyboard for button in row
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

    assert message.answers == []
    assert len(message.edits) == 1
    buttons = [
        button for row in message.edits[0].kwargs["reply_markup"].inline_keyboard for button in row
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


async def test_offsets_message_shows_saved_values_and_six_prayer_buttons() -> None:
    handler = getattr(handlers_module, "handle_offsets", None)
    repository = InMemorySubscriptions(
        UserSubscription(7, 9, "Toshkent", True, id=1, offsets=PrayerOffsets(shom=4))
    )
    message = FakeMessage()

    assert handler is not None
    await handler(message, make_services(repository))

    assert message.answers[0].text == (
        "⏱ Vaqtlarni sozlash\n\nO‘zgartirmoqchi bo‘lgan namoz vaqtini tanlang:"
    )
    buttons = [
        button
        for row in message.answers[0].kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert len(buttons) == 6
    assert buttons[4].callback_data == "offset:shom"


async def test_offsets_callback_edits_existing_message_with_overview() -> None:
    handler = getattr(handlers_module, "handle_offsets_overview", None)
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    message = FakeMessage()
    callback = FakeCallback("offsets", message)

    assert handler is not None
    await handler(callback, make_services(repository))

    assert callback.answered is True
    assert len(message.edits) == 1
    assert message.answers == []
    assert "O‘zgartirmoqchi bo‘lgan namoz vaqtini tanlang:" in message.edits[0].text


async def test_offset_selection_edits_message_with_minute_controls() -> None:
    handler = getattr(handlers_module, "handle_offset_selection", None)
    repository = InMemorySubscriptions(
        UserSubscription(7, 9, "Toshkent", True, id=1, offsets=PrayerOffsets(shom=4))
    )
    message = FakeMessage()
    callback = FakeCallback("offset:shom", message)

    assert handler is not None
    await handler(callback, make_services(repository))

    assert message.edits[0].text == (
        "⏱ Shom vaqtini sozlash\n\n"
        "Asl vaqt: 19:12\n"
        "Sozlangan vaqt: 19:16\n"
        "Joriy farq: +4 daqiqa\n\n"
        "\N{MINUS SIGN}1/+1 — vaqtni o‘zgartiradi, 0 — asl vaqt."
    )
    buttons = [
        button for row in message.edits[0].kwargs["reply_markup"].inline_keyboard for button in row
    ]
    assert [button.callback_data for button in buttons[:3]] == [
        "offset-change:shom:-1",
        "offset-change:shom:0",
        "offset-change:shom:1",
    ]
    assert buttons[-1].callback_data == "offset-schedule"


async def test_offset_change_supports_repeated_increment_and_selected_reset() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    services = make_services(repository)
    message = FakeMessage()

    assert handler is not None
    for _ in range(4):
        await handler(FakeCallback("offset-change:shom:1", message), services)

    assert repository.item is not None
    assert repository.item.offsets == PrayerOffsets(shom=4)
    assert len(message.edits) == 4
    assert "Asl vaqt: 19:12" in message.edits[-1].text
    assert "Sozlangan vaqt: 19:16" in message.edits[-1].text
    assert "Joriy farq: +4 daqiqa" in message.edits[-1].text

    await handler(FakeCallback("offset-change:shom:0", message), services)
    assert repository.item.offsets == PrayerOffsets()


async def test_offset_schedule_replaces_settings_with_adjusted_today_schedule() -> None:
    handler = getattr(handlers_module, "handle_offset_schedule", None)
    repository = InMemorySubscriptions(
        UserSubscription(7, 9, "Toshkent", True, id=1, offsets=PrayerOffsets(shom=4))
    )
    message = FakeMessage()
    callback = FakeCallback("offset-schedule", message)

    assert handler is not None
    await handler(callback, make_services(repository))

    assert callback.answered is True
    assert message.answers == []
    assert len(message.edits) == 1
    assert "📅 Bugun — 27-avgust, Toshkent" in message.edits[0].text
    assert "Shom — 19:16 (+4 daqiqa)" in message.edits[0].text
    assert message.edits[0].kwargs == {"reply_markup": None}


async def test_offset_change_boundary_alert_does_not_save_or_edit() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    repository = InMemorySubscriptions(
        UserSubscription(7, 9, "Toshkent", True, id=1, offsets=PrayerOffsets(shom=30))
    )
    message = FakeMessage()
    callback = FakeCallback("offset-change:shom:1", message)

    assert handler is not None
    await handler(callback, make_services(repository))

    assert repository.save_calls == 0
    assert message.edits == []
    assert callback.answer_text == "Chegara: \N{MINUS SIGN}30…+30 daqiqa"
    assert callback.answer_kwargs == {"show_alert": True}


@pytest.mark.parametrize(
    "data",
    [
        "offset:saharlik",
        "offset:shom:extra",
        "offset-change:saharlik:1",
        "offset-change:shom:2",
        "offset-change:shom:1:extra",
    ],
)
async def test_offset_callbacks_reject_untrusted_payloads(data: str) -> None:
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    message = FakeMessage()
    callback = FakeCallback(data, message)
    handler_name = (
        "handle_offset_change" if data.startswith("offset-change:") else "handle_offset_selection"
    )
    handler = getattr(handlers_module, handler_name, None)

    assert handler is not None
    await handler(callback, make_services(repository))

    assert repository.save_calls == 0
    assert message.edits == []
    assert callback.answer_kwargs == {"show_alert": True}


async def test_offset_callback_rejects_missing_message() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    callback = FakeCallback("offset-change:shom:1", None)

    assert handler is not None
    await handler(
        callback,
        make_services(InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))),
    )

    assert callback.answer_kwargs == {"show_alert": True}


async def test_offset_persistence_failure_is_not_acknowledged() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    repository = InMemorySubscriptions(
        UserSubscription(7, 9, "Toshkent", True, id=1),
        fail_save=True,
    )
    callback = FakeCallback("offset-change:shom:1", FakeMessage())

    assert handler is not None
    with pytest.raises(RuntimeError, match="database unavailable"):
        await handler(callback, make_services(repository))

    assert callback.answered is False


class FailingTodayProvider(ScheduleProvider):
    async def get_today(self, region_code: str) -> PrayerSchedule:
        raise ExternalServiceError(f"provider unavailable for {region_code}")


class TrackingTodayProvider(ScheduleProvider):
    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0

    async def get_today(self, region_code: str) -> PrayerSchedule:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0)
        try:
            return await super().get_today(region_code)
        finally:
            self.in_flight -= 1


async def test_offset_change_does_not_write_when_provider_fails() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    callback = FakeCallback("offset-change:shom:1", FakeMessage())

    assert handler is not None
    with pytest.raises(ExternalServiceError):
        await handler(callback, make_services(repository, FailingTodayProvider()))

    assert repository.item is not None
    assert repository.item.offsets == PrayerOffsets()
    assert repository.save_calls == 0
    assert callback.answered is False


async def test_offset_changes_are_serialized_per_user() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    provider = TrackingTodayProvider()
    services = make_services(repository, provider)
    message = FakeMessage()

    assert handler is not None
    await asyncio.gather(
        handler(FakeCallback("offset-change:shom:1", message), services),
        handler(FakeCallback("offset-change:shom:1", message), services),
    )

    assert repository.item is not None
    assert repository.item.offsets == PrayerOffsets(shom=2)
    assert provider.max_in_flight == 1
    assert "Joriy farq: +2 daqiqa" in message.edits[-1].text


async def test_zero_at_zero_is_acknowledged_without_write_or_identical_edit() -> None:
    handler = getattr(handlers_module, "handle_offset_change", None)
    repository = InMemorySubscriptions(UserSubscription(7, 9, "Toshkent", True, id=1))
    message = FakeMessage()
    callback = FakeCallback("offset-change:shom:0", message)

    assert handler is not None
    await handler(callback, make_services(repository))

    assert repository.save_calls == 0
    assert message.edits == []
    assert callback.answered is True
