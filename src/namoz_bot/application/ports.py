"""Dependency-inversion ports owned by the application layer."""

from datetime import date, datetime, time
from typing import Protocol

from namoz_bot.domain.daily_schedule import DailySchedulePreference, DailyScheduleRecipient
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    OffsetAction,
    PrayerKey,
    PrayerSchedule,
    UserSubscription,
)
from namoz_bot.domain.religious_intervals import ReligiousInterval


class DailyScheduleRepository(Protocol):
    async def ensure_defaults(self, at: time, now: datetime) -> None: ...

    async def get(self, telegram_user_id: int) -> DailySchedulePreference: ...

    async def set_time(
        self, telegram_user_id: int, at: time, now: datetime
    ) -> DailySchedulePreference: ...

    async def list_due(self, now: datetime, *, limit: int) -> list[DailyScheduleRecipient]: ...

    async def claim(self, item: DailyScheduleRecipient, now: datetime) -> bool: ...


class ReligiousIntervalRepository(Protocol):
    async def ensure_defaults(self, hours: float, now: datetime) -> None: ...

    async def get(self, telegram_user_id: int) -> ReligiousInterval: ...

    async def set_interval(
        self, telegram_user_id: int, hours: float, now: datetime
    ) -> ReligiousInterval: ...

    async def list_due(self, now: datetime, *, limit: int) -> list[ReligiousInterval]: ...

    async def claim(self, item: ReligiousInterval, now: datetime) -> bool: ...


class PrayerScheduleProvider(Protocol):
    """Fetch prayer schedules without exposing transport details."""

    async def get_today(self, region_code: str) -> PrayerSchedule:
        """Return the provider's current-day schedule for a region."""
        ...

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        """Return the provider schedule for the requested region and date."""
        ...


class ReligiousReminderProvider(Protocol):
    """Generate a short religious reflection without transport details."""

    async def generate(self) -> str: ...


class SubscriptionRepository(Protocol):
    """Persist subscriptions without exposing ORM details."""

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None: ...

    async def add(self, subscription: UserSubscription) -> UserSubscription: ...

    async def upsert_start(
        self, subscription: UserSubscription
    ) -> tuple[UserSubscription, bool]: ...

    async def save(self, subscription: UserSubscription) -> UserSubscription: ...

    async def change_offset(
        self,
        telegram_user_id: int,
        prayer: PrayerKey,
        action: OffsetAction,
    ) -> UserSubscription: ...

    async def change_region(
        self,
        telegram_user_id: int,
        region_code: str,
    ) -> UserSubscription: ...

    async def set_active(
        self,
        telegram_user_id: int,
        active: bool,
    ) -> UserSubscription: ...

    async def list_active_page(
        self,
        *,
        after_id: int,
        limit: int,
    ) -> list[UserSubscription]: ...


class DeliveryRepository(Protocol):
    """Reserve and track idempotent outgoing messages."""

    async def claim_batch(
        self,
        user_ids: list[int],
        schedule_date: date,
        delivery_type: DeliveryType,
    ) -> set[int]: ...

    async def mark_status(
        self,
        user_id: int,
        schedule_date: date,
        delivery_type: DeliveryType,
        status: DeliveryStatus,
        *,
        error_code: str | None = None,
    ) -> None: ...


class MessageSender(Protocol):
    """Send plain Telegram messages without exposing aiogram."""

    async def send(self, chat_id: int, text: str) -> None: ...
