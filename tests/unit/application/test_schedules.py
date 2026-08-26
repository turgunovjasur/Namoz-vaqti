from datetime import date

import pytest

from namoz_bot.application.schedules import ScheduleService, apply_offsets, format_schedule
from namoz_bot.domain.errors import (
    ScheduleDateMismatchError,
    ScheduleRegionMismatchError,
    ScheduleValidationError,
)
from namoz_bot.domain.models import PrayerOffsets, PrayerSchedule, PrayerTimes


def make_schedule(
    *,
    schedule_date: date = date(2026, 8, 27),
    region_code: str = "Toshkent",
    region_name: str = "Toshkent",
) -> PrayerSchedule:
    return PrayerSchedule(
        date=schedule_date,
        region_code=region_code,
        region_name=region_name,
        times=PrayerTimes(
            bomdod="04:17",
            quyosh="05:42",
            peshin="12:25",
            asr="17:10",
            shom="19:12",
            xufton="20:32",
        ),
    )


class StubProvider:
    def __init__(self, schedule: PrayerSchedule) -> None:
        self.schedule = schedule

    async def get_today(self, region_code: str) -> PrayerSchedule:
        return self.schedule

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        return self.schedule


@pytest.mark.asyncio
async def test_schedule_service_rejects_response_for_wrong_date() -> None:
    service = ScheduleService(StubProvider(make_schedule(schedule_date=date(2026, 8, 26))))

    with pytest.raises(ScheduleDateMismatchError):
        await service.get_schedule("Toshkent", date(2026, 8, 27))


@pytest.mark.asyncio
async def test_schedule_service_rejects_stale_year_at_new_year_boundary() -> None:
    service = ScheduleService(StubProvider(make_schedule(schedule_date=date(2026, 1, 1))))

    with pytest.raises(ScheduleDateMismatchError):
        await service.get_schedule("Toshkent", date(2027, 1, 1))


@pytest.mark.asyncio
async def test_schedule_service_rejects_response_for_wrong_region() -> None:
    service = ScheduleService(
        StubProvider(make_schedule(region_code="Samarqand", region_name="Samarqand"))
    )

    with pytest.raises(ScheduleRegionMismatchError):
        await service.get_schedule("Toshkent", date(2026, 8, 27))


def test_format_schedule_uses_numeric_date_and_parenthesized_region() -> None:
    text = format_schedule(make_schedule())

    assert text == (
        "📅 27.08.2026 (Toshkent)\n\n"
        "Bomdod — 04:17\n"
        "Quyosh — 05:42\n"
        "Peshin — 12:25\n"
        "Asr — 17:10\n"
        "Shom — 19:12\n"
        "Xufton — 20:32\n\n"
        "Manba: namoz-vaqti.uz"
    )


def test_apply_offsets_adjusts_all_six_values_without_mutating_canonical_schedule() -> None:
    schedule = make_schedule()

    adjusted = apply_offsets(
        schedule,
        PrayerOffsets(bomdod=-2, quyosh=-1, peshin=1, asr=2, shom=3, xufton=4),
    )

    assert adjusted.times == PrayerTimes("04:15", "05:41", "12:26", "17:12", "19:15", "20:36")
    assert schedule.times == PrayerTimes("04:17", "05:42", "12:25", "17:10", "19:12", "20:32")


def test_format_schedule_marks_only_adjusted_values() -> None:
    text = format_schedule(
        make_schedule(),
        PrayerOffsets(shom=4, xufton=-2),
    )

    assert "Shom — 19:16 (+4 daqiqa)" in text
    assert "Xufton — 20:30 (\N{MINUS SIGN}2 daqiqa)" in text
    assert "Asr — 17:10\n" in text
    assert "Asr — 17:10 (" not in text


def test_apply_offsets_rejects_crossing_day_boundary() -> None:
    schedule = PrayerSchedule(
        date=date(2026, 8, 27),
        region_code="Toshkent",
        region_name="Toshkent",
        times=PrayerTimes("00:10", "05:42", "12:25", "17:10", "19:12", "23:45"),
    )

    with pytest.raises(ScheduleValidationError):
        apply_offsets(schedule, PrayerOffsets(bomdod=-11))


def test_apply_offsets_rejects_broken_prayer_order() -> None:
    schedule = PrayerSchedule(
        date=date(2026, 8, 27),
        region_code="Toshkent",
        region_name="Toshkent",
        times=PrayerTimes("04:17", "05:42", "12:25", "17:10", "19:12", "19:30"),
    )

    with pytest.raises(ScheduleValidationError):
        apply_offsets(schedule, PrayerOffsets(shom=19))
