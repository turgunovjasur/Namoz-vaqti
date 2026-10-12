"""Manual generation cooldown and periodic religious broadcasts."""

import asyncio
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from namoz_bot.application.broadcasting import BroadcastReport
from namoz_bot.application.ports import (
    MessageSender,
    ReligiousIntervalRepository,
    ReligiousReminderProvider,
    SubscriptionRepository,
)
from namoz_bot.domain.errors import RecipientBlockedError, ReligiousReminderCooldownError
from namoz_bot.domain.models import UserSubscription
from namoz_bot.domain.religious_intervals import ReligiousInterval, validate_interval

logger = logging.getLogger(__name__)


def format_religious_reminder(reminder: str) -> str:
    return f"📖 Diniy eslatma\n\n{reminder}"


class ReligiousReminderService:
    """Reserve each user's manual request before awaiting the provider."""

    def __init__(
        self,
        provider: ReligiousReminderProvider,
        *,
        cooldown_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._next_allowed: dict[int, float] = {}
        self._in_flight: set[int] = set()

    def check_cooldown(self, telegram_user_id: int) -> None:
        """Reject an early press before presentation sends a loading message."""
        now = self._clock()
        remaining = math.ceil(self._next_allowed.get(telegram_user_id, now) - now)
        if telegram_user_id in self._in_flight or remaining > 0:
            raise ReligiousReminderCooldownError(max(1, remaining))

    async def generate(self, telegram_user_id: int) -> str:
        self.check_cooldown(telegram_user_id)
        now = self._clock()
        # No await before these reservations: concurrent requests cannot race.
        self._next_allowed[telegram_user_id] = now + self._cooldown_seconds
        self._in_flight.add(telegram_user_id)
        try:
            return await self._provider.generate()
        finally:
            self._in_flight.discard(telegram_user_id)


class ReligiousBroadcastService:
    """Generate once per interval and send the same text to active subscribers."""

    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        provider: ReligiousReminderProvider,
        sender: MessageSender,
        *,
        batch_size: int = 500,
        max_concurrency: int = 10,
    ) -> None:
        self._subscriptions = subscriptions
        self._provider = provider
        self._sender = sender
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def send(self) -> BroadcastReport:
        logger.info("religious_broadcast_started")
        cursor = 0
        text: str | None = None
        skipped = 0
        counts = {"sent": 0, "deactivated": 0, "failed": 0}
        while True:
            page = await self._subscriptions.list_active_page(
                after_id=cursor, limit=self._batch_size
            )
            if not page:
                break
            recipients = [item for item in page if item.id is not None]
            skipped += len(page) - len(recipients)
            if not recipients:
                break
            cursor = max(item.id for item in recipients if item.id is not None)
            if text is None:
                try:
                    text = format_religious_reminder(await self._provider.generate())
                except Exception as exc:
                    logger.warning(
                        "religious_broadcast_generation_failed error=%s", type(exc).__name__
                    )
                    raise
            results = await asyncio.gather(*(self._send_one(item, text) for item in recipients))
            for outcome in results:
                counts[outcome] += 1
            if len(page) < self._batch_size:
                break
        report = BroadcastReport(
            sent=counts["sent"],
            skipped=skipped,
            deactivated=counts["deactivated"],
            failed=counts["failed"],
        )
        logger.info(
            "religious_broadcast_complete sent=%d skipped=%d deactivated=%d failed=%d",
            report.sent,
            report.skipped,
            report.deactivated,
            report.failed,
        )
        return report

    async def _send_one(
        self, subscription: UserSubscription | ReligiousInterval, text: str
    ) -> Literal["sent", "deactivated", "failed"]:
        try:
            async with self._semaphore:
                try:
                    await self._sender.send(subscription.chat_id, text)
                except RecipientBlockedError:
                    await self._subscriptions.set_active(subscription.telegram_user_id, False)
                    return "deactivated"
        except Exception as exc:
            logger.warning("religious_broadcast_recipient_failed error=%s", type(exc).__name__)
            return "failed"
        return "sent"


class ReligiousIntervalService:
    def __init__(
        self,
        repository: ReligiousIntervalRepository,
        *,
        default_hours: float = 24,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        validate_interval(default_hours)
        self._repository = repository
        self._default_hours = default_hours
        self._clock = clock

    async def initialize(self) -> None:
        await self._repository.ensure_defaults(self._default_hours, self._clock())

    async def get(self, telegram_user_id: int) -> ReligiousInterval:
        await self.initialize()
        return await self._repository.get(telegram_user_id)

    async def set_interval(self, telegram_user_id: int, hours: float) -> ReligiousInterval:
        return await self._repository.set_interval(telegram_user_id, hours, self._clock())


class PersonalReligiousBroadcastService(ReligiousBroadcastService):
    """Poll durable personal schedules; missed intervals produce at most one send."""

    def __init__(
        self,
        intervals: ReligiousIntervalRepository,
        subscriptions: SubscriptionRepository,
        provider: ReligiousReminderProvider,
        sender: MessageSender,
        *,
        default_hours: float = 24,
        batch_size: int = 500,
        max_concurrency: int = 10,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(
            subscriptions, provider, sender, batch_size=batch_size, max_concurrency=max_concurrency
        )
        self._intervals = intervals
        self._default_hours = default_hours
        self._clock = clock

    async def send(self) -> BroadcastReport:
        now = self._clock()
        await self._intervals.ensure_defaults(self._default_hours, now)
        text: str | None = None
        sent = deactivated = failed = skipped = 0
        while items := await self._intervals.list_due(now, limit=self._batch_size):
            if text is None:
                text = format_religious_reminder(await self._provider.generate())

            outcomes = await asyncio.gather(*(self._send_due(item, now, text) for item in items))
            sent += outcomes.count("sent")
            deactivated += outcomes.count("deactivated")
            failed += outcomes.count("failed")
            skipped += outcomes.count("skipped")
            if len(items) < self._batch_size:
                break
        logger.info(
            "religious_broadcast_complete sent=%d skipped=%d deactivated=%d failed=%d",
            sent,
            skipped,
            deactivated,
            failed,
        )
        return BroadcastReport(sent=sent, skipped=skipped, deactivated=deactivated, failed=failed)

    async def _send_due(self, item: ReligiousInterval, now: datetime, text: str) -> str:
        # Recheck stored settings after Gemini and reserve before sending.
        if not await self._intervals.claim(item, now):
            return "skipped"
        return await self._send_one(item, text)
