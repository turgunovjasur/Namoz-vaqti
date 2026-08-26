"""Prayer schedule validation and presentation-neutral formatting."""

from datetime import date

from namoz_bot.application.ports import PrayerScheduleProvider
from namoz_bot.domain.errors import ScheduleDateMismatchError, ScheduleRegionMismatchError
from namoz_bot.domain.models import PrayerSchedule

_UZBEK_MONTHS = (
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentabr",
    "oktabr",
    "noyabr",
    "dekabr",
)


class ScheduleService:
    """Validate schedules returned by an external provider."""

    def __init__(self, provider: PrayerScheduleProvider) -> None:
        self._provider = provider

    async def get_today(self, region_code: str, expected_date: date) -> PrayerSchedule:
        """Fetch today's dedicated endpoint and validate its local date."""

        schedule = await self._provider.get_today(region_code)
        return self._validate(schedule, region_code, expected_date)

    async def get_schedule(self, region_code: str, target_date: date) -> PrayerSchedule:
        schedule = await self._provider.get_for_date(region_code, target_date)
        return self._validate(schedule, region_code, target_date)

    @staticmethod
    def _validate(
        schedule: PrayerSchedule,
        region_code: str,
        expected_date: date,
    ) -> PrayerSchedule:
        if schedule.date != expected_date:
            raise ScheduleDateMismatchError(
                "Kutilgan sana "
                f"{expected_date.isoformat()}, qaytgan sana {schedule.date.isoformat()}"
            )
        if schedule.region_code != region_code:
            raise ScheduleRegionMismatchError(
                f"Kutilgan hudud {region_code}, qaytgan hudud {schedule.region_code}"
            )
        return schedule


def format_schedule(schedule: PrayerSchedule, relative_label: str) -> str:
    """Render the canonical Uzbek daily schedule message."""

    month_name = _UZBEK_MONTHS[schedule.date.month - 1]
    times = schedule.times
    return (
        f"📅 {relative_label} — {schedule.date.day}-{month_name}, {schedule.region_name}\n\n"
        f"Bomdod — {times.bomdod}\n"
        f"Quyosh — {times.quyosh}\n"
        f"Peshin — {times.peshin}\n"
        f"Asr — {times.asr}\n"
        f"Shom — {times.shom}\n"
        f"Xufton — {times.xufton}\n\n"
        "Manba: islomapi.uz"
    )
