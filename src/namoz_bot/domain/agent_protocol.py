"""Versioned, owner-independent routing decisions and trusted agent envelopes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from namoz_bot.domain.accounting import MAX_AMOUNT, AccountingRequest, Category
from namoz_bot.domain.models import PrayerKey, PrayerOffsets
from namoz_bot.domain.regions import get_region
from namoz_bot.domain.reminders import parse_time

Domain = Literal["prayer", "reminder", "accounting", "settings", "assistant"]
Status = Literal["done", "needs_input", "needs_confirmation", "unsupported", "error", "cancelled"]


def _valid_month(value: str | None) -> str | None:
    return AccountingRequest.valid_month(value)


def _valid_date(value: str | None) -> str | None:
    return AccountingRequest.valid_date(value)


def _aware_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Timezone-aware time required")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class EmptyParameters(StrictModel):
    pass


class FinanceParameters(StrictModel):
    amount: int | None = Field(default=None, ge=1, le=MAX_AMOUNT)
    currency: Literal["UZS", "OTHER"] | None = None
    category: Category | None = None
    description: str | None = Field(default=None, min_length=1, max_length=300)
    month: str | None = None
    date: str | None = None

    _month = field_validator("month")(_valid_month)
    _date = field_validator("date")(_valid_date)


class ReportParameters(StrictModel):
    month: str | None = None
    report_type: Literal["summary", "income", "expense", "salary"] = "summary"

    _month = field_validator("month")(_valid_month)


class PageParameters(StrictModel):
    page: int = Field(default=0, ge=0, le=100000)


class ReminderParameters(StrictModel):
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    time: str | None = None
    date: str | None = None
    kind: Literal["once", "daily", "weekly"] | None = None
    weekdays: list[int] = Field(default_factory=list, max_length=7)

    _date = field_validator("date")(_valid_date)

    @field_validator("time")
    @classmethod
    def valid_time(cls, value: str | None) -> str | None:
        if value is not None:
            parse_time(value)
        return value

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, value: list[int]) -> list[int]:
        if any(type(day) is not int or not 0 <= day <= 6 for day in value):
            raise ValueError("Invalid weekday")
        return sorted(set(value))

    @model_validator(mode="after")
    def consistent_kind(self) -> "ReminderParameters":
        if self.date is not None and self.kind not in {None, "once"}:
            raise ValueError("Date conflicts with recurrence")
        if self.weekdays and self.kind not in {None, "weekly"}:
            raise ValueError("Weekdays conflict with recurrence")
        return self


class ScheduleParameters(StrictModel):
    date: str | None = None
    prayer: PrayerKey | None = None

    _date = field_validator("date")(_valid_date)


class ListParameters(PageParameters):
    today: bool = False


class ViewParameters(StrictModel):
    view: Literal["general", "region", "offsets", "interval", "daily"] = "general"


ACTION_MODELS: dict[tuple[str, str], type[StrictModel]] = {
    ("prayer", "schedule"): ScheduleParameters,
    ("prayer", "religious_excerpt"): EmptyParameters,
    ("prayer", "open_settings"): ViewParameters,
    ("reminder", "create"): ReminderParameters,
    ("reminder", "list"): ListParameters,
    ("reminder", "open_delete"): EmptyParameters,
    ("accounting", "income"): FinanceParameters,
    ("accounting", "expense"): FinanceParameters,
    ("accounting", "balance"): EmptyParameters,
    ("accounting", "report"): ReportParameters,
    ("accounting", "history"): PageParameters,
    ("settings", "open"): ViewParameters,
    **{
        ("assistant", action): EmptyParameters for action in ("help", "clarify", "cancel", "resume")
    },
}


class AgentDecision(StrictModel):
    domain: Domain
    action: str = Field(min_length=1, max_length=40)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    transcript: str = Field(min_length=1, max_length=2000)
    clarification: str | None = Field(default=None, min_length=1, max_length=300)
    multiple_tasks: bool = False

    @model_validator(mode="after")
    def validate_action(self) -> "AgentDecision":
        model = ACTION_MODELS.get((self.domain, self.action))
        if model is None:
            raise ValueError("Unsupported domain/action pair")
        # Preserve only explicitly supplied fields: omission must not clear a pending draft.
        self.parameters = model.model_validate(self.parameters).model_dump(
            mode="json", exclude_unset=True
        )
        return self


class AgentContext(StrictModel):
    bot_id: int = Field(gt=0)
    telegram_user_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    message_time: datetime
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    language: str = Field(default="uz", max_length=16)
    region_code: str
    offsets: PrayerOffsets = Field(default_factory=PrayerOffsets)

    @field_validator("message_time")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timezone-aware time required")
        return value

    @field_validator("region_code")
    @classmethod
    def known_region(cls, value: str) -> str:
        get_region(value)
        return value

    @model_validator(mode="after")
    def private_owner(self) -> "AgentContext":
        if self.chat_id != self.telegram_user_id:
            raise ValueError("Agent is private-chat only")
        return self


class AgentRequest(AgentDecision):
    protocol_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=100)
    operation_id: str = Field(min_length=1, max_length=32)
    context: AgentContext


class AgentResult(StrictModel):
    protocol_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=100)
    operation_id: str = Field(min_length=1, max_length=32)
    domain: Domain
    action: str
    status: Status
    data: dict[str, JsonValue] = Field(default_factory=dict)
    question: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    error_code: str | None = None
    retryable: bool = False
    effect: Literal["none", "committed", "unknown"] = "none"

    @model_validator(mode="after")
    def coherent_result(self) -> "AgentResult":
        if (self.domain, self.action) not in ACTION_MODELS:
            raise ValueError("Unsupported result action")
        if self.status == "needs_input" and (not self.question or not self.missing_fields):
            raise ValueError("Missing input requires a question and fields")
        if self.status == "needs_confirmation" and not self.data.get("draft"):
            raise ValueError("Confirmation requires a draft")
        if self.status == "error" and not self.error_code:
            raise ValueError("Error requires a code")
        if self.effect == "committed" and self.status != "done":
            raise ValueError("Only completed operations can be committed")
        if self.effect == "unknown" and self.status != "error":
            raise ValueError("Unknown effect requires error")
        return self


class AgentSessionState(StrictModel):
    operation_id: str = Field(min_length=1, max_length=32)
    origin_source_key: str = Field(min_length=1, max_length=64)
    origin_time: datetime
    domain: Domain
    action: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    revision: int = Field(ge=1)
    expires_at: datetime

    _origin = field_validator("origin_time")(_aware_time)
    _expiry = field_validator("expires_at")(_aware_time)


class AgentRevisionConflict(Exception):
    """An operation changed since the input or confirmation was prepared."""
