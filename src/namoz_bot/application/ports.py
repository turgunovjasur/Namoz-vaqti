"""Dependency-inversion ports owned by the application layer."""

from datetime import date
from typing import Protocol

from namoz_bot.domain.models import PrayerSchedule


class PrayerScheduleProvider(Protocol):
    """Fetch prayer schedules without exposing transport details."""

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        """Return the provider schedule for the requested region and date."""
        ...
