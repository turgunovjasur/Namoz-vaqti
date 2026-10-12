"""Validate extracted voice fields before they enter a personal reminder draft."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from namoz_bot.domain.reminders import parse_time


class VoiceReminderDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    transcript: str = Field(min_length=1, max_length=2000)
    intent: Literal["create_reminder", "unsupported", "unclear"]
    text: str | None = Field(min_length=1, max_length=1000)
    time: str | None
    date: str | None
    kind: Literal["once", "daily", "weekly"] | None
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(max_length=7)
    clarification: str | None = Field(min_length=1, max_length=300)

    @field_validator("time")
    @classmethod
    def valid_time(cls, value: str | None) -> str | None:
        if value is not None:
            parse_time(value)
        return value

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str | None) -> str | None:
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Sana YYYY-MM-DD shaklida bo‘lsin.")
        return value

    @model_validator(mode="after")
    def consistent_schedule(self) -> "VoiceReminderDraft":
        if self.date is not None and self.kind != "once":
            raise ValueError("Aniq sana faqat bir martalik eslatma uchun.")
        if self.weekdays and self.kind != "weekly":
            raise ValueError("Hafta kunlari faqat haftalik eslatma uchun.")
        self.weekdays = sorted(set(self.weekdays))
        return self
