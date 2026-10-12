from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


@pytest.mark.parametrize(
    "hours, expected",
    [(1, (2026, 10, 9, 16)), (6, (2026, 10, 9, 21)), (24, (2026, 10, 10, 15))],
)
def test_interval_starts_from_current_hour_boundary(hours, expected):
    import namoz_bot.domain.religious_intervals as module

    now = datetime(2026, 10, 9, 15, 40, 17, tzinfo=ZoneInfo("Asia/Tashkent"))
    assert hasattr(module, "next_interval_time"), "Hourly alignment is not implemented"
    assert module.next_interval_time(now, hours) == datetime(*expected, tzinfo=now.tzinfo)


def test_fractional_interval_is_rejected_to_keep_every_send_on_the_hour():
    from namoz_bot.domain.religious_intervals import validate_interval

    with pytest.raises(ValueError):
        validate_interval(1.5)
