from datetime import UTC, date, datetime, time

import pytest

from namoz_bot.domain.reminders import ReminderSpec, parse_time


@pytest.mark.parametrize(
    ("spec", "now", "expected"),
    [
        (
            ReminderSpec("Book", time(20), "daily"),
            "2026-09-23T15:01:00+00:00",
            "2026-09-24T15:00:00+00:00",
        ),
        (
            ReminderSpec("Book", time(0), "daily"),
            "2026-12-31T18:59:00+00:00",
            "2026-12-31T19:00:00+00:00",
        ),
        (
            ReminderSpec("Call", time(18), "weekly", weekdays=(6,)),
            "2026-09-27T13:00:00+00:00",
            "2026-10-04T13:00:00+00:00",
        ),
        (
            ReminderSpec("Call", time(18), "weekly", weekdays=(6,)),
            "2026-09-23T15:01:00+00:00",
            "2026-09-27T13:00:00+00:00",
        ),
        (
            ReminderSpec("Leap", time(10), "once", on_date=date(2028, 2, 29)),
            "2028-02-28T15:00:00+00:00",
            "2028-02-29T05:00:00+00:00",
        ),
    ],
)
def test_next_occurrence_obeys_tashkent_wall_clock(spec, now, expected):
    assert spec.next_after(datetime.fromisoformat(now)) == datetime.fromisoformat(expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": " "},
        {"text": "a" * 1001},
        {"kind": "monthly"},
        {"kind": "weekly", "weekdays": (7,)},
        {"kind": "weekly"},
        {"kind": "once"},
        {"on_date": date(2026, 9, 25)},
        {"weekdays": (0, 2)},
        {"at": time(10, 0, 1)},
    ],
)
def test_invalid_spec_rejected(kwargs):
    values = {"text": "Book", "at": time(20), "kind": "daily"} | kwargs
    with pytest.raises(ValueError):
        ReminderSpec(**values)


def test_past_once_and_naive_clock_rejected():
    spec = ReminderSpec("Book", time(20), "once", on_date=date(2026, 9, 23))
    with pytest.raises(ValueError):
        spec.next_after(datetime(2026, 9, 23, 15, tzinfo=UTC))
    with pytest.raises(ValueError):
        spec.next_after(datetime(2026, 9, 23))


@pytest.mark.parametrize("value", ["24:00", "20:60", "9:00", "no", "12:00:01"])
def test_invalid_time_rejected(value):
    with pytest.raises(ValueError):
        parse_time(value)


def test_time_accepts_midnight_and_last_minute():
    assert parse_time("00:00") == time(0)
    assert parse_time("23:59") == time(23, 59)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-09-23T14:59:00+00:00", "2026-09-23T15:00:00+00:00"),
        ("2026-09-23T15:00:00+00:00", "2026-09-25T15:00:00+00:00"),
        ("2026-09-25T15:01:00+00:00", "2026-09-28T15:00:00+00:00"),
        ("2026-09-27T19:01:00+00:00", "2026-09-28T15:00:00+00:00"),
    ],
)
def test_multiple_weekdays_pick_nearest_selected_day(now, expected):
    spec = ReminderSpec("Book", time(20), "weekly", weekdays=(4, 0, 2))
    assert spec.next_after(datetime.fromisoformat(now)) == datetime.fromisoformat(expected)
    assert spec.weekdays == (0, 2, 4)
    assert spec.schedule_label() == "Har hafta, Dushanba, Chorshanba, Juma"


@pytest.mark.parametrize("days", [(), (-1,), (7,), (True,), (1.5,)])
def test_weekly_requires_valid_nonempty_days(days):
    with pytest.raises(ValueError):
        ReminderSpec("Book", time(20), "weekly", weekdays=days)


def test_all_weekdays_advance_to_tomorrow_once_at_boundary():
    spec = ReminderSpec("Book", time(0), "weekly", weekdays=tuple(range(7)))
    assert spec.next_after(datetime(2026, 12, 31, 19, tzinfo=UTC)) == datetime(
        2027, 1, 1, 19, tzinfo=UTC
    )
