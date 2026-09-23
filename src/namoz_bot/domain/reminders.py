"""Personal reminder validation and recurrence, independent of Telegram and SQL."""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")
WEEKDAYS = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")


def parse_time(value: str) -> time:
    if not re.fullmatch(r"[0-9]{2}:[0-9]{2}", value.strip()):
        raise ValueError("Vaqtni HH:MM shaklida kiriting, masalan 20:00.")
    try:
        return time.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("Soat 00:00–23:59 oralig‘ida bo‘lishi kerak.") from exc


@dataclass(frozen=True, slots=True)
class ReminderSpec:
    text: str
    at: time
    kind: str
    on_date: date | None = None
    weekdays: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", self.text.strip())
        if not 1 <= len(self.text) <= 1000:
            raise ValueError("Eslatma matni 1–1000 belgidan iborat bo‘lsin.")
        if self.at.second or self.at.microsecond or self.at.tzinfo:
            raise ValueError("Vaqtni HH:MM shaklida kiriting.")
        if any(type(day) is not int or not 0 <= day <= 6 for day in self.weekdays):
            raise ValueError("Hafta kunlari noto‘g‘ri.")
        object.__setattr__(self, "weekdays", tuple(sorted(set(self.weekdays))))
        valid = (
            (self.kind == "once" and self.on_date is not None and not self.weekdays)
            or (self.kind == "daily" and self.on_date is None and not self.weekdays)
            or (self.kind == "weekly" and self.on_date is None and bool(self.weekdays))
        )
        if not valid:
            raise ValueError("Sana yoki takrorlanish tartibi noto‘g‘ri.")

    def next_after(self, now: datetime) -> datetime:
        if now.tzinfo is None:
            raise ValueError("Vaqt zonasi ko‘rsatilishi kerak.")
        local = now.astimezone(TASHKENT)
        target = self.on_date or local.date()
        if self.kind == "weekly":
            candidates = []
            for day in self.weekdays:
                selected = target + timedelta(days=(day - target.weekday()) % 7)
                candidate = datetime.combine(selected, self.at, TASHKENT)
                if candidate <= local:
                    candidate += timedelta(days=7)
                candidates.append(candidate)
            return min(candidates).astimezone(UTC)
        candidate = datetime.combine(target, self.at, TASHKENT)
        if candidate <= local:
            if self.kind == "once":
                raise ValueError("Tanlangan sana va vaqt o‘tib ketgan. Kelajak vaqtini tanlang.")
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)

    def schedule_label(self) -> str:
        if self.kind == "once":
            assert self.on_date is not None
            return f"{self.on_date:%d.%m.%Y} · {WEEKDAYS[self.on_date.weekday()]}"
        if self.kind == "weekly":
            return "Har hafta, " + ", ".join(WEEKDAYS[day] for day in self.weekdays)
        return "Har kuni"


@dataclass(frozen=True, slots=True)
class Reminder:
    id: int
    user_id: int
    spec: ReminderSpec
    next_due: datetime | None
    status: str


@dataclass(frozen=True, slots=True)
class ReminderDelivery:
    id: int
    reminder_id: int
    user_id: int
    chat_id: int
    text: str
