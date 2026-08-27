import asyncio
from datetime import date

from namoz_bot.application.broadcasting import BroadcastService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.domain.errors import ExternalServiceError, RecipientBlockedError
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    OffsetAction,
    PrayerKey,
    PrayerOffsets,
    PrayerSchedule,
    PrayerTimes,
    UserSubscription,
)


class Subscriptions:
    def __init__(self, users: list[UserSubscription]) -> None:
        self.users = {user.telegram_user_id: user for user in users}

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None:
        return self.users.get(telegram_user_id)

    async def add(self, subscription: UserSubscription) -> UserSubscription:
        self.users[subscription.telegram_user_id] = subscription
        return subscription

    async def upsert_start(self, subscription: UserSubscription) -> tuple[UserSubscription, bool]:
        existing = self.users.get(subscription.telegram_user_id)
        if existing is None:
            self.users[subscription.telegram_user_id] = subscription
            return subscription, True
        saved = UserSubscription(
            telegram_user_id=existing.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=existing.region_code,
            is_active=True,
            id=existing.id,
            offsets=existing.offsets,
        )
        self.users[saved.telegram_user_id] = saved
        return saved, False

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self.users[subscription.telegram_user_id] = subscription
        return subscription

    async def change_offset(
        self,
        telegram_user_id: int,
        prayer: PrayerKey,
        action: OffsetAction,
    ) -> UserSubscription:
        subscription = self.users[telegram_user_id]
        return await self.save(
            subscription.with_preferences(
                offsets=subscription.offsets.change(prayer, action),
            )
        )

    async def change_region(
        self,
        telegram_user_id: int,
        region_code: str,
    ) -> UserSubscription:
        subscription = self.users[telegram_user_id]
        return await self.save(
            subscription.with_preferences(region_code=region_code, offsets=PrayerOffsets())
        )

    async def set_active(
        self,
        telegram_user_id: int,
        active: bool,
    ) -> UserSubscription:
        subscription = self.users[telegram_user_id]
        return await self.save(subscription.with_preferences(is_active=active))

    async def list_active_page(self, *, after_id: int, limit: int) -> list[UserSubscription]:
        active = sorted(
            (
                user
                for user in self.users.values()
                if user.is_active and user.id is not None and user.id > after_id
            ),
            key=lambda user: user.id or 0,
        )
        return active[:limit]


class Deliveries:
    def __init__(self, fail_status_for: set[int] | None = None) -> None:
        self.statuses: dict[tuple[int, date, DeliveryType], DeliveryStatus] = {}
        self.fail_status_for = fail_status_for or set()

    async def claim_batch(
        self,
        user_ids: list[int],
        schedule_date: date,
        delivery_type: DeliveryType,
    ) -> set[int]:
        claimed: set[int] = set()
        for user_id in user_ids:
            key = (user_id, schedule_date, delivery_type)
            if key not in self.statuses:
                self.statuses[key] = DeliveryStatus.PENDING
                claimed.add(user_id)
        return claimed

    async def mark_status(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
        status: DeliveryStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        if user_id in self.fail_status_for:
            raise RuntimeError("database unavailable")
        self.statuses[(user_id, schedule_date, delivery_type)] = status


class Provider:
    def __init__(
        self,
        failed_regions: set[str] | None = None,
        times: PrayerTimes | None = None,
    ) -> None:
        self.failed_regions = failed_regions or set()
        self.times = times or PrayerTimes(
            "04:17",
            "05:42",
            "12:25",
            "17:10",
            "19:12",
            "20:32",
        )
        self.calls: list[tuple[str, date]] = []

    async def get_today(self, region_code: str) -> PrayerSchedule:
        return await self.get_for_date(region_code, date.today())

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        self.calls.append((region_code, target_date))
        await asyncio.sleep(0)
        if region_code in self.failed_regions:
            raise ExternalServiceError("provider unavailable")
        return PrayerSchedule(
            date=target_date,
            region_code=region_code,
            region_name=region_code,
            times=self.times,
        )


class Sender:
    def __init__(self, blocked_chat_id: int | None = None) -> None:
        self.blocked_chat_id = blocked_chat_id
        self.messages: list[tuple[int, str]] = []

    async def send(self, chat_id: int, text: str) -> None:
        if chat_id == self.blocked_chat_id:
            raise RecipientBlockedError("blocked")
        self.messages.append((chat_id, text))


def user(
    identifier: int,
    region: str = "Toshkent",
    offsets: PrayerOffsets | None = None,
) -> UserSubscription:
    return UserSubscription(
        id=identifier,
        telegram_user_id=identifier,
        chat_id=identifier * 10,
        region_code=region,
        is_active=True,
        offsets=offsets or PrayerOffsets(),
    )


async def test_broadcast_fetches_each_region_once_and_sends_each_user_once() -> None:
    subscriptions = Subscriptions([user(1), user(2), user(3, "Samarqand")])
    deliveries = Deliveries()
    provider = Provider()
    sender = Sender()
    service = BroadcastService(
        subscriptions,
        deliveries,
        ScheduleService(provider),
        sender,
        batch_size=2,
    )

    first = await service.send_next_day(date(2026, 8, 27))
    second = await service.send_next_day(date(2026, 8, 27))

    assert provider.calls == [
        ("Toshkent", date(2026, 8, 27)),
        ("Samarqand", date(2026, 8, 27)),
    ]
    assert len(sender.messages) == 3
    assert first.sent == 3
    assert second.skipped == 3


async def test_broadcast_formats_distinct_offsets_after_one_region_fetch() -> None:
    subscriptions = Subscriptions([user(1), user(2, offsets=PrayerOffsets(shom=4))])
    deliveries = Deliveries()
    provider = Provider()
    sender = Sender()

    report = await BroadcastService(
        subscriptions,
        deliveries,
        ScheduleService(provider),
        sender,
    ).send_next_day(date(2026, 8, 27))

    assert provider.calls == [("Toshkent", date(2026, 8, 27))]
    messages = {chat_id: text for chat_id, text in sender.messages}
    assert report.sent == 2
    assert messages[10] != messages[20]
    assert "(+4 daqiqa)" not in messages[10]
    assert "Shom   — 19:16 (+4 daqiqa)" in messages[20]


async def test_invalid_personal_adjustment_fails_only_that_delivery() -> None:
    subscriptions = Subscriptions(
        [
            user(1, offsets=PrayerOffsets(bomdod=-11)),
            user(2),
        ]
    )
    deliveries = Deliveries()
    provider = Provider(times=PrayerTimes("00:10", "05:42", "12:25", "17:10", "19:12", "20:32"))
    sender = Sender()
    target_date = date(2026, 8, 27)

    report = await BroadcastService(
        subscriptions,
        deliveries,
        ScheduleService(provider),
        sender,
    ).send_next_day(target_date)

    assert report.sent == 1
    assert report.failed == 1
    assert [chat_id for chat_id, _ in sender.messages] == [20]
    assert deliveries.statuses[(1, target_date, DeliveryType.DAILY)] is DeliveryStatus.FAILED
    assert deliveries.statuses[(2, target_date, DeliveryType.DAILY)] is DeliveryStatus.SENT


async def test_pending_claim_is_not_retried_after_restart() -> None:
    subscriptions = Subscriptions([user(1)])
    deliveries = Deliveries()
    await deliveries.claim_batch([1], date(2026, 8, 27), DeliveryType.DAILY)
    sender = Sender()

    report = await BroadcastService(
        subscriptions, deliveries, ScheduleService(Provider()), sender
    ).send_next_day(date(2026, 8, 27))

    assert report.skipped == 1
    assert sender.messages == []


async def test_status_persistence_failure_does_not_stop_later_pages() -> None:
    subscriptions = Subscriptions([user(1), user(2)])
    deliveries = Deliveries(fail_status_for={1})
    sender = Sender()

    report = await BroadcastService(
        subscriptions,
        deliveries,
        ScheduleService(Provider()),
        sender,
        batch_size=1,
    ).send_next_day(date(2026, 8, 27))

    assert report.failed == 1
    assert report.sent == 1
    assert [chat_id for chat_id, _ in sender.messages] == [10, 20]
    assert deliveries.statuses[(2, date(2026, 8, 27), DeliveryType.DAILY)] is DeliveryStatus.SENT


async def test_failed_region_does_not_stop_other_regions() -> None:
    subscriptions = Subscriptions([user(1), user(2, "Samarqand")])
    deliveries = Deliveries()
    provider = Provider(failed_regions={"Samarqand"})
    sender = Sender()

    report = await BroadcastService(
        subscriptions, deliveries, ScheduleService(provider), sender
    ).send_next_day(date(2026, 8, 27))

    assert report.sent == 1
    assert report.failed == 1
    assert report.failed_regions == ("Samarqand",)
    assert [chat_id for chat_id, _ in sender.messages] == [10]


async def test_blocked_chat_is_deactivated_without_stopping_batch() -> None:
    subscriptions = Subscriptions([user(1), user(2)])
    deliveries = Deliveries()
    sender = Sender(blocked_chat_id=10)

    report = await BroadcastService(
        subscriptions, deliveries, ScheduleService(Provider()), sender
    ).send_next_day(date(2026, 8, 27))

    assert report.deactivated == 1
    assert report.sent == 1
    assert subscriptions.users[1].is_active is False
