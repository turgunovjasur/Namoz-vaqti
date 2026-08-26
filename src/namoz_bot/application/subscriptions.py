"""User onboarding and preference use cases."""

from dataclasses import dataclass, replace

from namoz_bot.application.ports import SubscriptionRepository
from namoz_bot.domain.errors import SubscriptionNotFoundError
from namoz_bot.domain.models import UserSubscription
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
        existing = await self._repository.get_by_telegram_user_id(telegram_user_id)
        if existing is None:
            created = await self._repository.add(
                UserSubscription(
                    telegram_user_id=telegram_user_id,
                    chat_id=chat_id,
                    region_code=DEFAULT_REGION_CODE,
                    is_active=True,
                )
            )
            return StartResult(subscription=created, created=True)

        reactivated = replace(existing, chat_id=chat_id, is_active=True)
        saved = await self._repository.save(reactivated)
        return StartResult(subscription=saved, created=False)

    async def get(self, telegram_user_id: int) -> UserSubscription:
        subscription = await self._repository.get_by_telegram_user_id(telegram_user_id)
        if subscription is None:
            raise SubscriptionNotFoundError("Foydalanuvchi avval /start buyrug‘ini yuborishi kerak")
        return subscription

    async def change_region(self, telegram_user_id: int, region_code: str) -> UserSubscription:
        get_region(region_code)
        subscription = await self.get(telegram_user_id)
        return await self._repository.save(replace(subscription, region_code=region_code))

    async def set_active(self, telegram_user_id: int, active: bool) -> UserSubscription:
        subscription = await self.get(telegram_user_id)
        return await self._repository.save(replace(subscription, is_active=active))
