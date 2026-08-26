"""Daily APScheduler wiring."""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from namoz_bot.application.broadcasting import BroadcastReport


def build_daily_trigger(send_time: time, timezone: str) -> CronTrigger:
    """Build the exact local-time cron trigger."""

    return CronTrigger(
        hour=send_time.hour,
        minute=send_time.minute,
        timezone=ZoneInfo(timezone),
    )


def calculate_target_date(local_now: datetime) -> date:
    """Return the next local calendar date."""

    return (local_now + timedelta(days=1)).date()


def create_scheduler(
    run_broadcast: Callable[[date], Awaitable[BroadcastReport]],
    *,
    send_time: time,
    timezone: str,
) -> AsyncIOScheduler:
    """Create, but do not start, the application scheduler."""

    local_timezone = ZoneInfo(timezone)
    scheduler = AsyncIOScheduler(timezone=local_timezone)

    async def daily_job() -> None:
        await run_broadcast(calculate_target_date(datetime.now(local_timezone)))

    scheduler.add_job(
        daily_job,
        trigger=build_daily_trigger(send_time, timezone),
        id="daily-prayer-schedule",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
