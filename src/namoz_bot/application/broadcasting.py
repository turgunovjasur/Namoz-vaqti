"""Grouped and idempotent daily broadcast use case."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from namoz_bot.application.ports import (
    DeliveryRepository,
    MessageSender,
    SubscriptionRepository,
)
from namoz_bot.application.schedules import ScheduleService, format_schedule
from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.domain.models import DeliveryStatus, DeliveryType, UserSubscription


@dataclass(frozen=True, slots=True)
class BroadcastReport:
    """Operational counters returned by one daily broadcast."""

    sent: int = 0
    skipped: int = 0
    deactivated: int = 0
    failed: int = 0
    failed_regions: tuple[str, ...] = ()


class BroadcastService:
    """Send one next-day schedule to every active subscription."""

    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        deliveries: DeliveryRepository,
        schedules: ScheduleService,
        sender: MessageSender,
    ) -> None:
        self._subscriptions = subscriptions
        self._deliveries = deliveries
        self._schedules = schedules
        self._sender = sender

    async def send_next_day(self, target_date: date) -> BroadcastReport:
        users_by_region: dict[str, list[UserSubscription]] = defaultdict(list)
        skipped = 0
        for subscription in await self._subscriptions.list_active():
            if subscription.id is None:
                skipped += 1
                continue
            reserved = await self._deliveries.reserve(
                subscription.id, target_date, DeliveryType.DAILY
            )
            if reserved:
                users_by_region[subscription.region_code].append(subscription)
            else:
                skipped += 1

        sent = 0
        deactivated = 0
        failed = 0
        failed_regions: list[str] = []
        for region_code, subscriptions in users_by_region.items():
            try:
                schedule = await self._schedules.get_schedule(region_code, target_date)
            except Exception as exc:
                failed_regions.append(region_code)
                failed += len(subscriptions)
                for subscription in subscriptions:
                    await self._mark_failed(subscription, target_date, type(exc).__name__)
                continue

            text = format_schedule(schedule, relative_label="Ertaga")
            for subscription in subscriptions:
                try:
                    await self._sender.send(subscription.chat_id, text)
                except RecipientBlockedError:
                    await self._subscriptions.save(subscription.with_preferences(is_active=False))
                    await self._mark_failed(subscription, target_date, "recipient_blocked")
                    deactivated += 1
                except Exception as exc:
                    await self._mark_failed(subscription, target_date, type(exc).__name__)
                    failed += 1
                else:
                    assert subscription.id is not None
                    await self._deliveries.mark_status(
                        subscription.id,
                        target_date,
                        DeliveryType.DAILY,
                        DeliveryStatus.SENT,
                    )
                    sent += 1

        return BroadcastReport(
            sent=sent,
            skipped=skipped,
            deactivated=deactivated,
            failed=failed,
            failed_regions=tuple(failed_regions),
        )

    async def _mark_failed(
        self,
        subscription: UserSubscription,
        target_date: date,
        error_code: str,
    ) -> None:
        if subscription.id is None:
            return
        await self._deliveries.mark_status(
            subscription.id,
            target_date,
            DeliveryType.DAILY,
            DeliveryStatus.FAILED,
            error_code=error_code[:100],
        )
