"""Paged, bounded, and idempotent daily broadcast use case."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from namoz_bot.application.ports import (
    DeliveryRepository,
    MessageSender,
    SubscriptionRepository,
)
from namoz_bot.application.schedules import ScheduleService, format_schedule
from namoz_bot.domain.errors import RecipientBlockedError, ScheduleValidationError
from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    PrayerSchedule,
    UserSubscription,
)

logger = logging.getLogger(__name__)


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
        *,
        batch_size: int = 500,
        max_concurrency: int = 10,
    ) -> None:
        self._subscriptions = subscriptions
        self._deliveries = deliveries
        self._schedules = schedules
        self._sender = sender
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def send_next_day(self, target_date: date) -> BroadcastReport:
        schedule_cache: dict[str, PrayerSchedule | Exception] = {}
        failed_regions: list[str] = []
        cursor = 0
        sent = 0
        skipped = 0
        deactivated = 0
        failed = 0

        while True:
            page = await self._subscriptions.list_active_page(
                after_id=cursor,
                limit=self._batch_size,
            )
            if not page:
                break
            page_ids = [item.id for item in page if item.id is not None]
            if not page_ids:
                skipped += len(page)
                break
            cursor = max(page_ids)
            claimed_ids = await self._deliveries.claim_batch(
                page_ids,
                target_date,
                DeliveryType.DAILY,
            )
            skipped += len(page_ids) - len(claimed_ids)
            claimed = [item for item in page if item.id in claimed_ids]

            for region_code in dict.fromkeys(item.region_code for item in claimed):
                if region_code not in schedule_cache:
                    schedule_cache[region_code] = await self._prepare_schedule(
                        region_code,
                        target_date,
                    )

            results = await asyncio.gather(
                *(self._send_one(item, target_date, schedule_cache) for item in claimed)
            )
            for outcome, region_code in results:
                if outcome == "sent":
                    sent += 1
                elif outcome == "deactivated":
                    deactivated += 1
                else:
                    failed += 1
                    if outcome == "region_failed" and region_code not in failed_regions:
                        failed_regions.append(region_code)

            if len(page) < self._batch_size:
                break

        return BroadcastReport(
            sent=sent,
            skipped=skipped,
            deactivated=deactivated,
            failed=failed,
            failed_regions=tuple(failed_regions),
        )

    async def _prepare_schedule(
        self,
        region_code: str,
        target_date: date,
    ) -> PrayerSchedule | Exception:
        try:
            schedule = await self._schedules.get_schedule(region_code, target_date)
        except Exception as exc:
            logger.exception(
                "broadcast_region_schedule_failed region=%s date=%s error=%s",
                region_code,
                target_date.isoformat(),
                type(exc).__name__,
            )
            return exc
        return schedule

    async def _send_one(
        self,
        subscription: UserSubscription,
        target_date: date,
        schedule_cache: dict[str, PrayerSchedule | Exception],
    ) -> tuple[str, str]:
        try:
            return await self._send_one_workflow(subscription, target_date, schedule_cache)
        except Exception as exc:
            logger.exception(
                "broadcast_workflow_persistence_failed region=%s error=%s",
                subscription.region_code,
                type(exc).__name__,
            )
            return "failed", subscription.region_code

    async def _send_one_workflow(
        self,
        subscription: UserSubscription,
        target_date: date,
        schedule_cache: dict[str, PrayerSchedule | Exception],
    ) -> tuple[str, str]:
        region_code = subscription.region_code
        cached = schedule_cache[region_code]

        if isinstance(cached, Exception):
            await self._mark_failed(subscription, target_date, type(cached).__name__)
            return "region_failed", region_code

        try:
            text = format_schedule(
                cached,
                offsets=subscription.offsets,
            )
        except ScheduleValidationError as exc:
            logger.exception(
                "broadcast_recipient_schedule_failed region=%s error=%s",
                region_code,
                type(exc).__name__,
            )
            await self._mark_failed(subscription, target_date, type(exc).__name__)
            return "failed", region_code

        async with self._semaphore:
            try:
                await self._sender.send(subscription.chat_id, text)
            except RecipientBlockedError:
                logger.info("broadcast_recipient_deactivated region=%s", region_code)
                await self._subscriptions.set_active(subscription.telegram_user_id, False)
                await self._mark_failed(subscription, target_date, "recipient_blocked")
                return "deactivated", region_code
            except Exception as exc:
                logger.exception(
                    "broadcast_recipient_failed region=%s error=%s",
                    region_code,
                    type(exc).__name__,
                )
                await self._mark_failed(subscription, target_date, type(exc).__name__)
                return "failed", region_code

        assert subscription.id is not None
        await self._deliveries.mark_status(
            subscription.id,
            target_date,
            DeliveryType.DAILY,
            DeliveryStatus.SENT,
        )
        return "sent", region_code

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
