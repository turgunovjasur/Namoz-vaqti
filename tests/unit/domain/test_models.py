from datetime import date

import pytest

from namoz_bot.domain.errors import ScheduleValidationError
from namoz_bot.domain.models import PrayerSchedule, PrayerTimes, UserSubscription


def test_prayer_times_reject_invalid_clock_value() -> None:
    with pytest.raises(ScheduleValidationError, match="Bomdod"):
        PrayerTimes(
            bomdod="25:00",
            quyosh="06:00",
            peshin="12:00",
            asr="16:00",
            shom="18:00",
            xufton="20:00",
        )


def test_prayer_times_reject_non_chronological_values() -> None:
    with pytest.raises(ScheduleValidationError, match="ketma-ket"):
        PrayerTimes(
            bomdod="05:00",
            quyosh="06:00",
            peshin="12:00",
            asr="11:59",
            shom="18:00",
            xufton="20:00",
        )


def test_prayer_schedule_is_immutable() -> None:
    schedule = PrayerSchedule(
        date=date(2026, 8, 27),
        region_code="Toshkent",
        region_name="Toshkent",
        times=PrayerTimes(
            bomdod="04:17",
            quyosh="05:42",
            peshin="12:25",
            asr="17:10",
            shom="19:12",
            xufton="20:32",
        ),
    )

    with pytest.raises(AttributeError):
        schedule.region_code = "Samarqand"  # type: ignore[misc]


def test_user_subscription_can_be_copied_with_changed_preferences() -> None:
    subscription = UserSubscription(
        telegram_user_id=10,
        chat_id=20,
        region_code="Toshkent",
        is_active=True,
    )

    changed = subscription.with_preferences(region_code="Samarqand", is_active=False)

    assert changed.region_code == "Samarqand"
    assert changed.is_active is False
    assert subscription.region_code == "Toshkent"
