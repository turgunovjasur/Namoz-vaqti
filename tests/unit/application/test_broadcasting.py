from datetime import date

from namoz_bot.application.broadcasting import BroadcastService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.domain.errors import ExternalServiceError, RecipientBlockedError
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
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

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self.users[subscription.telegram_user_id] = subscription
        return subscription

    async def list_active(self) -> list[UserSubscription]:
        return [user for user in self.users.values() if user.is_active]


class Deliveries:
    def __init__(self) -> None:
        self.statuses: dict[tuple[int, date, DeliveryType], DeliveryStatus] = {}

    async def reserve(self, user_id: int, schedule_date: date, delivery_type: DeliveryType) -> bool:
        key = (user_id, schedule_date, delivery_type)
        if self.statuses.get(key) is DeliveryStatus.SENT:
            return False
        self.statuses[key] = DeliveryStatus.PENDING
        return True

    async def mark_status(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
        status: DeliveryStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        self.statuses[(user_id, schedule_date, delivery_type)] = status


class Provider:
    def __init__(self, failed_regions: set[str] | None = None) -> None:
        self.failed_regions = failed_regions or set()
        self.calls: list[tuple[str, date]] = []

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        self.calls.append((region_code, target_date))
        if region_code in self.failed_regions:
            raise ExternalServiceError("provider unavailable")
        return PrayerSchedule(
            date=target_date,
            region_code=region_code,
            region_name=region_code,
            times=PrayerTimes("04:17", "05:42", "12:25", "17:10", "19:12", "20:32"),
        )


class Sender:
    def __init__(self, blocked_chat_id: int | None = None) -> None:
        self.blocked_chat_id = blocked_chat_id
        self.messages: list[tuple[int, str]] = []

    async def send(self, chat_id: int, text: str) -> None:
        if chat_id == self.blocked_chat_id:
            raise RecipientBlockedError("blocked")
        self.messages.append((chat_id, text))


def user(identifier: int, region: str = "Toshkent") -> UserSubscription:
    return UserSubscription(
        id=identifier,
        telegram_user_id=identifier,
        chat_id=identifier * 10,
        region_code=region,
        is_active=True,
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
