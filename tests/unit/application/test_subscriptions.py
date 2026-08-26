from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.models import UserSubscription


class InMemorySubscriptionRepository:
    def __init__(self, existing: UserSubscription | None = None) -> None:
        self.items: dict[int, UserSubscription] = {}
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
        )
        self.items[stored.telegram_user_id] = stored
        return stored

    async def save(self, subscription: UserSubscription) -> UserSubscription:
        self.items[subscription.telegram_user_id] = subscription
        return subscription

    async def list_active(self) -> list[UserSubscription]:
        return [item for item in self.items.values() if item.is_active]


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
    )
    repository = InMemorySubscriptionRepository(existing)

    result = await SubscriptionService(repository).start(telegram_user_id=7, chat_id=9)

    assert result.created is False
    assert result.subscription.chat_id == 9
    assert result.subscription.region_code == "Samarqand"
    assert result.subscription.is_active is True


async def test_change_region_persists_catalog_code() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(telegram_user_id=7, chat_id=9, region_code="Toshkent", is_active=True)
    )

    changed = await SubscriptionService(repository).change_region(7, "Samarqand")

    assert changed.region_code == "Samarqand"
    assert repository.items[7].region_code == "Samarqand"


async def test_toggle_notifications_changes_active_state() -> None:
    repository = InMemorySubscriptionRepository(
        UserSubscription(telegram_user_id=7, chat_id=9, region_code="Toshkent", is_active=True)
    )
    service = SubscriptionService(repository)

    disabled = await service.set_active(7, False)
    enabled = await service.set_active(7, True)

    assert disabled.is_active is False
    assert enabled.is_active is True
