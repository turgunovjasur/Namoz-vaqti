"""User onboarding and preference use cases."""

from dataclasses import dataclass

from namoz_bot.application.ports import SubscriptionRepository
from namoz_bot.domain.errors import SubscriptionNotFoundError
from namoz_bot.domain.models import OffsetAction, PrayerKey, PrayerOffsets, UserSubscription
from namoz_bot.domain.regions import DEFAULT_REGION_CODE, get_region


@dataclass(frozen=True, slots=True)
class StartResult:
    """Onboarding result used by the presentation layer."""

    subscription: UserSubscription
    created: bool


class SubscriptionService:
    """Manage idempotent Telegram subscriptions."""

    def __init__(self, repository: SubscriptionRepository) -> None:
        self._repository = repository

    async def start(self, telegram_user_id: int, chat_id: int) -> StartResult:
        subscription, created = await self._repository.upsert_start(
            UserSubscription(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                region_code=DEFAULT_REGION_CODE,
                is_active=True,
            )
        )
        return StartResult(subscription=subscription, created=created)

    async def get(self, telegram_user_id: int) -> UserSubscription:
        subscription = await self._repository.get_by_telegram_user_id(telegram_user_id)
        if subscription is None:
            raise SubscriptionNotFoundError("Foydalanuvchi avval /start buyrug‘ini yuborishi kerak")
        return subscription

    async def change_region(self, telegram_user_id: int, region_code: str) -> UserSubscription:
        get_region(region_code)
        subscription = await self.get(telegram_user_id)
        return await self._repository.save(
            subscription.with_preferences(
                region_code=region_code,
                offsets=PrayerOffsets(),
            )
        )

    async def change_offset(
        self,
        telegram_user_id: int,
        prayer: PrayerKey,
        action: OffsetAction,
    ) -> UserSubscription:
        """Apply one validated offset action and persist the aggregate once."""

        subscription = await self.get(telegram_user_id)
        offsets = subscription.offsets.change(prayer, action)
        return await self._repository.save(subscription.with_preferences(offsets=offsets))

    async def set_active(self, telegram_user_id: int, active: bool) -> UserSubscription:
        subscription = await self.get(telegram_user_id)
        return await self._repository.save(subscription.with_preferences(is_active=active))
