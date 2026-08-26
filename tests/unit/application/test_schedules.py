from datetime import date

import pytest

from namoz_bot.application.schedules import ScheduleService, format_schedule
from namoz_bot.domain.errors import ScheduleDateMismatchError, ScheduleRegionMismatchError
from namoz_bot.domain.models import PrayerSchedule, PrayerTimes


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


def test_format_schedule_uses_agreed_uzbek_copy() -> None:
    text = format_schedule(make_schedule(), relative_label="Ertaga")

    assert text == (
        "📅 Ertaga — 27-avgust, Toshkent\n\n"
        "Bomdod — 04:17\n"
        "Quyosh — 05:42\n"
        "Peshin — 12:25\n"
        "Asr — 17:10\n"
        "Shom — 19:12\n"
        "Xufton — 20:32\n\n"
        "Manba: namoz-vaqti.uz"
    )
