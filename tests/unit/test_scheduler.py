from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from namoz_bot.scheduler import build_daily_trigger, calculate_target_date


def test_daily_trigger_uses_configured_tashkent_time() -> None:
    trigger = build_daily_trigger(time(21, 0), "Asia/Tashkent")

    assert str(trigger.fields[5]) == "21"
    assert str(trigger.fields[6]) == "0"
    assert str(trigger.timezone) == "Asia/Tashkent"


def test_scheduler_targets_tomorrow_in_local_timezone() -> None:
    local_now = datetime(2026, 8, 26, 21, 0, tzinfo=ZoneInfo("Asia/Tashkent"))

    assert calculate_target_date(local_now) == date(2026, 8, 27)
