"""Prayer schedule validation and presentation-neutral formatting."""

from datetime import date

from namoz_bot.application.ports import PrayerScheduleProvider
from namoz_bot.domain.errors import (
    ScheduleDateMismatchError,
    ScheduleRegionMismatchError,
    ScheduleValidationError,
)
from namoz_bot.domain.models import PrayerOffsets, PrayerSchedule, PrayerTimes

UZBEK_WEEKDAYS = (
    "Dushanba",
    "Seshanba",
    "Chorshanba",
    "Payshanba",
    "Juma",
    "Shanba",
    "Yakshanba",
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


def _adjust_clock(clock: str, offset: int) -> str:
    hour, minute = (int(part) for part in clock.split(":"))
    adjusted = hour * 60 + minute + offset
    if not 0 <= adjusted < 24 * 60:
        raise ScheduleValidationError("Sozlangan vaqt kun chegarasidan chiqdi")
    adjusted_hour, adjusted_minute = divmod(adjusted, 60)
    return f"{adjusted_hour:02d}:{adjusted_minute:02d}"


def apply_offsets(schedule: PrayerSchedule, offsets: PrayerOffsets) -> PrayerSchedule:
    """Return a newly validated schedule with per-prayer minute offsets applied."""

    times = schedule.times
    return PrayerSchedule(
        date=schedule.date,
        region_code=schedule.region_code,
        region_name=schedule.region_name,
        times=PrayerTimes(
            bomdod=_adjust_clock(times.bomdod, offsets.bomdod),
            quyosh=_adjust_clock(times.quyosh, offsets.quyosh),
            peshin=_adjust_clock(times.peshin, offsets.peshin),
            asr=_adjust_clock(times.asr, offsets.asr),
            shom=_adjust_clock(times.shom, offsets.shom),
            xufton=_adjust_clock(times.xufton, offsets.xufton),
        ),
    )


def _offset_suffix(value: int) -> str:
    if value > 0:
        return f" (+{value} daqiqa)"
    if value < 0:
        return f" (\N{MINUS SIGN}{abs(value)} daqiqa)"
    return ""


def format_schedule(
    schedule: PrayerSchedule,
    offsets: PrayerOffsets | None = None,
) -> str:
    """Render an Uzbek daily schedule with optional personal adjustments."""

    configured_offsets = offsets or PrayerOffsets()
    times = apply_offsets(schedule, configured_offsets).times
    weekday = UZBEK_WEEKDAYS[schedule.date.weekday()]
    rows = (
        ("Bomdod", times.bomdod, configured_offsets.bomdod),
        ("Quyosh", times.quyosh, configured_offsets.quyosh),
        ("Peshin", times.peshin, configured_offsets.peshin),
        ("Asr", times.asr, configured_offsets.asr),
        ("Shom", times.shom, configured_offsets.shom),
        ("Xufton", times.xufton, configured_offsets.xufton),
    )
    label_width = max(len(label) for label, _, _ in rows)
    schedule_rows = "\n".join(
        f"{label:<{label_width}} — {clock}{_offset_suffix(offset)}" for label, clock, offset in rows
    )
    return (
        f"{schedule.date:%d.%m.%Y} ({weekday})\n"
        f"{schedule.region_name}\n\n"
        f"{schedule_rows}\n\n"
        "Manba: namoz-vaqti.uz"
    )
