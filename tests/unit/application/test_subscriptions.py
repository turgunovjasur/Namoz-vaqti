import pytest

from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.errors import ScheduleValidationError, SubscriptionNotFoundError
from namoz_bot.domain.models import OffsetAction, PrayerKey, PrayerOffsets, UserSubscription


class InMemorySubscriptionRepository:
    def __init__(self, existing: UserSubscription | None = None) -> None:
        self.items: dict[int, UserSubscription] = {}
        self.saved: list[UserSubscription] = []
        if existing is not None:
            self.items[existing.telegram_user_id] = existing

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> UserSubscription | None:
        return self.items.get(telegram_user_id)

    async def add(self, subscription: UserSubscription) -> UserSubscription:
        stored = UserSubscription(
            id=len(self.items) + 1,
            telegram_user_id=subscription.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=subscription.region_code,
            is_active=subscription.is_active,
            offsets=subscription.offsets,
        )
        self.items[stored.telegram_user_id] = stored
        return stored

    async def upsert_start(self, subscription: UserSubscription) -> tuple[UserSubscription, bool]:
        existing = self.items.get(subscription.telegram_user_id)
        if existing is None:
            return await self.add(subscription), True
        stored = UserSubscription(
            id=existing.id,
            telegram_user_id=existing.telegram_user_id,
            chat_id=subscription.chat_id,
            region_code=existing.region_code,
            is_active=True,
            offsets=existing.offsets,
        )
        self.items[stored.telegram_user_id] = stored
        return stored, False

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self.saved.append(subscription)
        self.items[subscription.telegram_user_id] = subscription
        return subscription

    async def change_offset(
        self,
        telegram_user_id: int,
        prayer: PrayerKey,
        action: OffsetAction,
    ) -> UserSubscription:
        subscription = self.items.get(telegram_user_id)
        if subscription is None:
            raise SubscriptionNotFoundError("Foydalanuvchi topilmadi")
        offsets = subscription.offsets.change(prayer, action)
        return await self.save(subscription.with_preferences(offsets=offsets))

    async def change_region(
        self,
        telegram_user_id: int,
        region_code: str,
    ) -> UserSubscription:
        subscription = self.items[telegram_user_id]
        return await self.save(
            subscription.with_preferences(region_code=region_code, offsets=PrayerOffsets())
        )

    async def set_active(
        self,
        telegram_user_id: int,
        active: bool,
    ) -> UserSubscription:
        subscription = self.items[telegram_user_id]
        return await self.save(subscription.with_preferences(is_active=active))

    async def list_active_page(self, *, after_id: int, limit: int) -> list[UserSubscription]:
        return [
            item
            for item in self.items.values()
            if item.is_active and item.id is not None and item.id > after_id
        ][:limit]


async def test_start_creates_active_tashkent_subscription_once() -> None:
    repository = InMemorySubscriptionRepository()
    service = SubscriptionService(repository)

    first = await service.start(telegram_user_id=7, chat_id=9)
    second = await service.start(telegram_user_id=7, chat_id=9)

    assert first.created is True
    assert second.created is False
    assert second.subscription.region_code == "Toshkent"
    assert second.subscription.is_active is True
    assert len(repository.items) == 1


async def test_returning_user_keeps_region_updates_chat_and_reactivates() -> None:
    existing = UserSubscription(
        id=1,
        telegram_user_id=7,
        chat_id=8,
        region_code="Samarqand",
        is_active=False,
        offsets=PrayerOffsets(shom=4),
    )
    repository = InMemorySubscriptionRepository(existing)

    result = await SubscriptionService(repository).start(telegram_user_id=7, chat_id=9)

    assert result.created is False
    assert result.subscription.chat_id == 9
    assert result.subscription.region_code == "Samarqand"
    assert result.subscription.is_active is True
    assert result.subscription.offsets == PrayerOffsets(shom=4)


async def test_change_region_persists_catalog_code() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(
            telegram_user_id=7,
            chat_id=9,
            region_code="Toshkent",
            is_active=True,
            offsets=PrayerOffsets(bomdod=-2, shom=4),
        )
    )

    changed = await SubscriptionService(repository).change_region(7, "Samarqand")

    assert changed.region_code == "Samarqand"
    assert changed.offsets == PrayerOffsets()
    assert repository.items[7].region_code == "Samarqand"
    assert repository.saved == [changed]


async def test_change_offset_updates_only_selected_prayer() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(7, 9, "Toshkent", True, offsets=PrayerOffsets(asr=-2))
    )
    service = SubscriptionService(repository)

    increased = await service.change_offset(7, "shom", 1)
    decreased = await service.change_offset(7, "shom", -1)

    assert increased.offsets == PrayerOffsets(asr=-2, shom=1)
    assert decreased.offsets == PrayerOffsets(asr=-2)


async def test_change_offset_zero_resets_only_selected_prayer() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(
            7,
            9,
            "Toshkent",
            True,
            offsets=PrayerOffsets(asr=-2, shom=4),
        )
    )

    reset = await SubscriptionService(repository).change_offset(7, "shom", 0)

    assert reset.offsets == PrayerOffsets(asr=-2)


async def test_change_offset_does_not_save_out_of_range_value() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(7, 9, "Toshkent", True, offsets=PrayerOffsets(shom=30))
    )

    with pytest.raises(ScheduleValidationError):
        await SubscriptionService(repository).change_offset(7, "shom", 1)

    assert repository.saved == []


async def test_change_offset_requires_existing_subscription() -> None:
    with pytest.raises(SubscriptionNotFoundError):
        await SubscriptionService(InMemorySubscriptionRepository()).change_offset(7, "shom", 1)


async def test_toggle_notifications_changes_active_state() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(telegram_user_id=7, chat_id=9, region_code="Toshkent", is_active=True)
    )
    service = SubscriptionService(repository)

    disabled = await service.set_active(7, False)
    enabled = await service.set_active(7, True)

    assert disabled.is_active is False
    assert enabled.is_active is True
