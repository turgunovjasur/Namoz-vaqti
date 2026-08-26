"""Immutable business entities shared by all adapters."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from namoz_bot.domain.errors import ScheduleValidationError

PrayerKey = Literal["bomdod", "quyosh", "peshin", "asr", "shom", "xufton"]
OffsetAction = Literal[-1, 0, 1]
PRAYER_KEYS: tuple[PrayerKey, ...] = (
    "bomdod",
    "quyosh",
    "peshin",
    "asr",
    "shom",
    "xufton",
)


@dataclass(frozen=True, slots=True)
class PrayerOffsets:
    """Per-prayer minute adjustments constrained to Telegram's supported range."""

    bomdod: int = 0
    quyosh: int = 0
    peshin: int = 0
    asr: int = 0
    shom: int = 0
    xufton: int = 0

    def __post_init__(self) -> None:
        for prayer in PRAYER_KEYS:
            value = self.value_for(prayer)
            if isinstance(value, bool) or not isinstance(value, int) or not -30 <= value <= 30:
                raise ScheduleValidationError(
                    f"{prayer} farqi \N{MINUS SIGN}30…+30 daqiqa oralig‘ida bo‘lishi kerak"
                )

    def value_for(self, prayer: PrayerKey) -> int:
        """Return one offset while rejecting untrusted runtime keys."""

        match prayer:
            case "bomdod":
                return self.bomdod
            case "quyosh":
                return self.quyosh
            case "peshin":
                return self.peshin
            case "asr":
                return self.asr
            case "shom":
                return self.shom
            case "xufton":
                return self.xufton
            case _:
                raise ScheduleValidationError("Sozlanadigan vaqt topilmadi")

    def change(self, prayer: PrayerKey, action: OffsetAction) -> "PrayerOffsets":
        """Increment, decrement, or reset exactly one prayer offset."""

        if action not in (-1, 0, 1):
            raise ScheduleValidationError("Offset amali noto‘g‘ri")
        current = self.value_for(prayer)
        value = 0 if action == 0 else current + action
        match prayer:
            case "bomdod":
                return replace(self, bomdod=value)
            case "quyosh":
                return replace(self, quyosh=value)
            case "peshin":
                return replace(self, peshin=value)
            case "asr":
                return replace(self, asr=value)
            case "shom":
                return replace(self, shom=value)
            case "xufton":
                return replace(self, xufton=value)
            case _:
                raise ScheduleValidationError("Sozlanadigan vaqt topilmadi")


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


class DeliveryType(StrEnum):
    """Kinds of messages protected by idempotent delivery tracking."""

    DAILY = "daily"
    ONBOARDING = "onboarding"


class DeliveryStatus(StrEnum):
    """Persistent state of one scheduled message."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
