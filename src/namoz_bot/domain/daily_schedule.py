"""Personal daily prayer schedule preferences."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from namoz_bot.domain.models import UserSubscription
from namoz_bot.domain.reminders import TASHKENT


def next_daily_time(at: time, now: datetime) -> datetime:
    if at.second or at.microsecond or at.tzinfo is not None:
        raise ValueError("Vaqtni HH:MM shaklida tanlang.")
    local = now.astimezone(TASHKENT)
    due = datetime.combine(local.date(), at, TASHKENT)
    if due <= local:
        due += timedelta(days=1)
    return due.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class DailySchedulePreference:
    user_id: int
    at: time
    next_due: datetime


@dataclass(frozen=True, slots=True)
class DailyScheduleRecipient:
    subscription: UserSubscription
    preference: DailySchedulePreference
