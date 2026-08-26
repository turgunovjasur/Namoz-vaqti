"""Immutable business entities shared by all adapters."""

from dataclasses import dataclass, replace
from datetime import date, datetime

from namoz_bot.domain.errors import ScheduleValidationError


@dataclass(frozen=True, slots=True)
class PrayerTimes:
    """Six daily prayer-related clock values in chronological order."""

    bomdod: str
    quyosh: str
    peshin: str
    asr: str
    shom: str
    xufton: str

    def __post_init__(self) -> None:
        labels_and_values = (
            ("Bomdod", self.bomdod),
            ("Quyosh", self.quyosh),
            ("Peshin", self.peshin),
            ("Asr", self.asr),
            ("Shom", self.shom),
            ("Xufton", self.xufton),
        )
        minutes: list[int] = []
        for label, value in labels_and_values:
            try:
                parsed = datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ScheduleValidationError(f"{label} vaqti noto‘g‘ri: {value}") from exc
            minutes.append(parsed.hour * 60 + parsed.minute)

        if minutes != sorted(minutes) or len(set(minutes)) != len(minutes):
            raise ScheduleValidationError("Namoz vaqtlarining ketma-ketligi noto‘g‘ri")


@dataclass(frozen=True, slots=True)
class PrayerSchedule:
    """A validated prayer schedule for one region and date."""

    date: date
    region_code: str
    region_name: str
    times: PrayerTimes


@dataclass(frozen=True, slots=True)
class UserSubscription:
    """A Telegram user's current delivery preferences."""

    telegram_user_id: int
    chat_id: int
    region_code: str
    is_active: bool
    id: int | None = None

    def with_preferences(
        self,
        *,
        region_code: str | None = None,
        is_active: bool | None = None,
    ) -> "UserSubscription":
        """Return an updated copy while keeping identity fields intact."""

        return replace(
            self,
            region_code=self.region_code if region_code is None else region_code,
            is_active=self.is_active if is_active is None else is_active,
        )
