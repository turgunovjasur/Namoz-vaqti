"""Personal daily delivery settings and recipient selection."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta

from namoz_bot.application.broadcasting import BroadcastReport, BroadcastService
from namoz_bot.application.ports import (
    DailyScheduleRepository,
    DeliveryRepository,
    MessageSender,
    SubscriptionRepository,
)
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.domain.daily_schedule import DailySchedulePreference
from namoz_bot.domain.reminders import TASHKENT

logger = logging.getLogger(__name__)


class DailyScheduleSettingsService:
    def __init__(
        self,
        repository: DailyScheduleRepository,
        *,
        default_time: time = time(21),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._default_time = default_time
        self._clock = clock

    async def initialize(self) -> None:
        await self._repository.ensure_defaults(self._default_time, self._clock())

    async def get(self, telegram_user_id: int) -> DailySchedulePreference:
        await self.initialize()
        return await self._repository.get(telegram_user_id)

    async def set_time(self, telegram_user_id: int, at: time) -> DailySchedulePreference:
        return await self._repository.set_time(telegram_user_id, at, self._clock())


class PersonalDailyBroadcastService:
    def __init__(
        self,
        preferences: DailyScheduleRepository,
        subscriptions: SubscriptionRepository,
        deliveries: DeliveryRepository,
        schedules: ScheduleService,
        sender: MessageSender,
        *,
        default_time: time = time(21),
        batch_size: int = 500,
        max_concurrency: int = 10,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._preferences = preferences
        self._default_time = default_time
        self._clock = clock
        self._batch_size = batch_size
        self._broadcast = BroadcastService(
            subscriptions,
            deliveries,
            schedules,
            sender,
            batch_size=batch_size,
            max_concurrency=max_concurrency,
        )

    async def send(self) -> BroadcastReport:
        now = self._clock()
        await self._preferences.ensure_defaults(self._default_time, now)
        target = (now.astimezone(TASHKENT) + timedelta(days=1)).date()
        sent = skipped = deactivated = failed = 0
        failed_regions: set[str] = set()
        while page := await self._preferences.list_due(now, limit=self._batch_size):
            recipients = []
            for item in page:
                if await self._preferences.claim(item, now):
                    recipients.append(item.subscription)
                else:
                    skipped += 1
            report = await self._broadcast.send_next_day(target, recipients=recipients)
            sent += report.sent
            skipped += report.skipped
            deactivated += report.deactivated
            failed += report.failed
            failed_regions.update(report.failed_regions)
            if len(page) < self._batch_size:
                break
        logger.info(
            "daily_broadcast_complete date=%s sent=%d skipped=%d deactivated=%d failed=%d",
            target,
            sent,
            skipped,
            deactivated,
            failed,
        )
        return BroadcastReport(sent, skipped, deactivated, failed, tuple(sorted(failed_regions)))
