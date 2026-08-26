"""In-memory adapters driving complete application flows in acceptance tests."""

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

from namoz_bot.application.broadcasting import BroadcastReport, BroadcastService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    PrayerSchedule,
    PrayerTimes,
    UserSubscription,
)
from namoz_bot.domain.regions import get_region, list_regions
from namoz_bot.presentation.handlers import (
    HandlerServices,
    handle_region_selection,
    handle_start,
)
from namoz_bot.scheduler import calculate_target_date


class InMemorySubscriptionRepository:
    """Minimal persistence adapter preserving production repository semantics."""

    def __init__(self) -> None:
        self._by_telegram_id: dict[int, UserSubscription] = {}
        self._next_id = 1

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None:
        return self._by_telegram_id.get(telegram_user_id)

    async def add(self, subscription: UserSubscription) -> UserSubscription:
        saved = UserSubscription(
            id=self._next_id,
            telegram_user_id=subscription.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=subscription.region_code,
            is_active=subscription.is_active,
        )
        self._next_id += 1
        self._by_telegram_id[saved.telegram_user_id] = saved
        return saved

    async def upsert_start(self, subscription: UserSubscription) -> tuple[UserSubscription, bool]:
        existing = self._by_telegram_id.get(subscription.telegram_user_id)
        if existing is None:
            return await self.add(subscription), True
        saved = UserSubscription(
            telegram_user_id=existing.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=existing.region_code,
            is_active=True,
            id=existing.id,
        )
        self._by_telegram_id[saved.telegram_user_id] = saved
        return saved, False

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self._by_telegram_id[subscription.telegram_user_id] = subscription
        return subscription

    async def list_active_page(self, *, after_id: int, limit: int) -> list[UserSubscription]:
        items = sorted(
            (
                item
                for item in self._by_telegram_id.values()
                if item.is_active and item.id is not None and item.id > after_id
            ),
            key=lambda item: item.id or 0,
        )
        return items[:limit]


class InMemoryDeliveryRepository:
    """Track daily delivery reservations across repeated scheduler runs."""

    def __init__(self) -> None:
        self._statuses: dict[tuple[int, date, DeliveryType], DeliveryStatus] = {}

    async def claim_batch(
        self,
        user_ids: list[int],
        schedule_date: date,
        delivery_type: DeliveryType,
    ) -> set[int]:
        claimed: set[int] = set()
        for user_id in user_ids:
            key = (user_id, schedule_date, delivery_type)
            if key not in self._statuses:
                self._statuses[key] = DeliveryStatus.PENDING
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
        del error_code
        self._statuses[(user_id, schedule_date, delivery_type)] = status


class FakeScheduleProvider:
    """Deterministic IslomAPI boundary used by all acceptance journeys."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, date]] = []

    async def get_today(self, region_code: str) -> PrayerSchedule:
        return await self.get_for_date(region_code, date(2026, 8, 26))

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        self.calls.append((region_code, target_date))
        return PrayerSchedule(
            date=target_date,
            region_code=region_code,
            region_name=get_region(region_code).display_name,
            times=PrayerTimes(
                bomdod="04:17",
                quyosh="05:46",
                peshin="12:27",
                asr="17:08",
                shom="19:03",
                xufton="20:27",
            ),
        )


class FakeSender:
    """Capture scheduled Telegram messages by chat."""

    def __init__(self, messages: dict[int, list[str]]) -> None:
        self._messages = messages

    async def send(self, chat_id: int, text: str) -> None:
        self._messages.setdefault(chat_id, []).append(text)


@dataclass(slots=True)
class FakeMessage:
    """Small aiogram Message substitute for handler-level acceptance tests."""

    user_id: int
    chat_id: int
    messages: dict[int, list[str]]

    @property
    def from_user(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.user_id)

    @property
    def chat(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.chat_id)

    async def answer(self, text: str, **kwargs: Any) -> None:
        del kwargs
        self.messages.setdefault(self.chat_id, []).append(text)


@dataclass(slots=True)
class FakeCallback:
    """Small aiogram CallbackQuery substitute for region selection."""

    data: str
    message: FakeMessage
    user_id: int

    @property
    def from_user(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.user_id)

    async def answer(self, text: str | None = None, **kwargs: Any) -> None:
        del text, kwargs


class AppHarness:
    """Compose real use cases and handlers around deterministic external adapters."""

    def __init__(self) -> None:
        self.today = date(2026, 8, 26)
        self._messages: dict[int, list[str]] = {}
        self._subscriptions = InMemorySubscriptionRepository()
        self._deliveries = InMemoryDeliveryRepository()
        self._provider = FakeScheduleProvider()
        self._schedule_service = ScheduleService(self._provider)
        self._subscription_service = SubscriptionService(self._subscriptions)
        self._handler_services = HandlerServices(
            subscriptions=self._subscription_service,
            schedules=self._schedule_service,
            today=lambda: self.today,
        )
        self._broadcast = BroadcastService(
            self._subscriptions,
            self._deliveries,
            self._schedule_service,
            FakeSender(self._messages),
        )

    async def start(self, *, user_id: int, chat_id: int) -> None:
        await handle_start(
            FakeMessage(user_id=user_id, chat_id=chat_id, messages=self._messages),
            self._handler_services,
        )

    async def select_region(
        self,
        *,
        user_id: int,
        chat_id: int,
        display_name: str,
    ) -> None:
        region_index = next(
            index
            for index, region in enumerate(list_regions())
            if region.display_name == display_name
        )
        callback = FakeCallback(
            data=f"region:0:{region_index}",
            message=FakeMessage(user_id=user_id, chat_id=chat_id, messages=self._messages),
            user_id=user_id,
        )
        await handle_region_selection(callback, self._handler_services)

    async def run_daily_job(self, local_time: str) -> BroadcastReport:
        target_date = calculate_target_date(datetime.fromisoformat(local_time))
        return await self._broadcast.send_next_day(target_date)

    def last_message(self, chat_id: int) -> str:
        return self._messages[chat_id][-1]

    def messages_for(self, chat_id: int) -> list[str]:
        return self._messages.get(chat_id, [])

    def clear_messages(self) -> None:
        self._messages.clear()

    def provider_calls_for(self, region_code: str, target_date: str) -> int:
        expected_date = date.fromisoformat(target_date)
        return self._provider.calls.count((region_code, expected_date))
