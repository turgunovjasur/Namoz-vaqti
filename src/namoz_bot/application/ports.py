"""Dependency-inversion ports owned by the application layer."""

from datetime import date
from typing import Protocol

from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    PrayerSchedule,
    UserSubscription,
)


class PrayerScheduleProvider(Protocol):
    """Fetch prayer schedules without exposing transport details."""

    async def get_today(self, region_code: str) -> PrayerSchedule:
        """Return the provider's current-day schedule for a region."""
        ...

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        """Return the provider schedule for the requested region and date."""
        ...


class SubscriptionRepository(Protocol):
    """Persist subscriptions without exposing ORM details."""

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None: ...

    async def add(self, subscription: UserSubscription) -> UserSubscription: ...

    async def upsert_start(
        self, subscription: UserSubscription
    ) -> tuple[UserSubscription, bool]: ...

    async def save(self, subscription: UserSubscription) -> UserSubscription: ...

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
