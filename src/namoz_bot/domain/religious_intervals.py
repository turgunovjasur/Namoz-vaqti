"""Personal religious reminder intervals, independent of prayer notifications."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta


def validate_interval(hours: float) -> None:
    if (
        isinstance(hours, bool)
        or not math.isfinite(hours)
        or not 0 <= hours <= 168
        or hours != int(hours)
    ):
        raise ValueError("Interval 1–168 soat bo‘lsin; o‘chirish uchun 0 tanlang.")


def next_interval_time(now: datetime, hours: float) -> datetime | None:
    validate_interval(hours)
    return (
        now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=hours) if hours else None
    )


@dataclass(frozen=True, slots=True)
class ReligiousInterval:
    user_id: int
    telegram_user_id: int
    chat_id: int
    interval_hours: float
    next_due: datetime | None
