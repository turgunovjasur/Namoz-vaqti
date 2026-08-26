import pytest

from namoz_bot.domain.errors import ScheduleValidationError
from namoz_bot.domain.models import PrayerOffsets


def test_prayer_offsets_default_every_prayer_to_zero() -> None:
    assert PrayerOffsets() == PrayerOffsets(0, 0, 0, 0, 0, 0)


def test_prayer_offsets_accept_inclusive_boundaries_and_distinct_values() -> None:
    offsets = PrayerOffsets(
        bomdod=-30,
        quyosh=-20,
        peshin=-10,
        asr=10,
        shom=20,
        xufton=30,
    )

    assert offsets.value_for("bomdod") == -30
    assert offsets.value_for("quyosh") == -20
    assert offsets.value_for("peshin") == -10
    assert offsets.value_for("asr") == 10
    assert offsets.value_for("shom") == 20
    assert offsets.value_for("xufton") == 30


def test_change_updates_only_selected_prayer_and_zero_resets_it() -> None:
    offsets = PrayerOffsets().change("shom", 1).change("shom", 1)

    assert offsets == PrayerOffsets(shom=2)
    assert offsets.change("shom", -1) == PrayerOffsets(shom=1)
    assert offsets.change("shom", 0) == PrayerOffsets()


@pytest.mark.parametrize("value", [-31, 31])
def test_prayer_offsets_reject_values_outside_supported_range(value: int) -> None:
    with pytest.raises(ScheduleValidationError):
        PrayerOffsets(shom=value)


@pytest.mark.parametrize("action", [-2, 2])
def test_change_rejects_unsupported_actions(action: int) -> None:
    with pytest.raises(ScheduleValidationError):
        PrayerOffsets().change("shom", action)  # type: ignore[arg-type]


@pytest.mark.parametrize("action", [False, True])
def test_change_rejects_boolean_actions(action: bool) -> None:
    with pytest.raises(ScheduleValidationError):
        PrayerOffsets().change("shom", action)  # type: ignore[arg-type]


def test_change_rejects_unsupported_prayer() -> None:
    with pytest.raises(ScheduleValidationError):
        PrayerOffsets().change("saharlik", 1)  # type: ignore[arg-type]
