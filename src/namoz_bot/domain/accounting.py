"""Whole-so'm ledger contracts; Gemini output never performs arithmetic."""

from dataclasses import dataclass
from datetime import date as calendar_date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from namoz_bot.domain.reminders import TASHKENT

MAX_AMOUNT = 10**15
CATEGORY_LABELS = {
    "oylik": "Oylik",
    "boshqa_kirim": "Boshqa kirim",
    "kiyim": "Kiyim",
    "oziq_ovqat": "Oziq-ovqat",
    "transport": "Transport",
    "uy_joy": "Uy-joy",
    "sogliq": "Sog‘liq",
    "talim": "Ta’lim",
    "aloqa": "Aloqa",
    "boshqa": "Boshqa",
}
Category = Literal[
    "oylik",
    "boshqa_kirim",
    "kiyim",
    "oziq_ovqat",
    "transport",
    "uy_joy",
    "sogliq",
    "talim",
    "aloqa",
    "boshqa",
]


class AccountingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    transcript: str = Field(min_length=1, max_length=2000)
    intent: Literal["income", "expense", "balance", "report", "history", "unclear", "unsupported"]
    amount: int | None = Field(ge=1, le=MAX_AMOUNT)
    currency: Literal["UZS", "OTHER"] | None
    category: Category | None
    description: str | None = Field(min_length=1, max_length=300)
    month: str | None
    date: str | None
    report_type: Literal["income", "expense", "salary", "summary"] | None
    clarification: str | None = Field(min_length=1, max_length=300)

    @field_validator("month")
    @classmethod
    def valid_month(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = calendar_date.fromisoformat(value + "-01")
            if parsed.isoformat()[:7] != value:
                raise ValueError("Oy YYYY-MM shaklida bo‘lsin.")
        return value

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str | None) -> str | None:
        if value is not None and calendar_date.fromisoformat(value).isoformat() != value:
            raise ValueError("Sana YYYY-MM-DD shaklida bo‘lsin.")
        return value

    @model_validator(mode="after")
    def consistent_period(self) -> "AccountingRequest":
        if self.date and self.month and self.date[:7] != self.month:
            raise ValueError("Sana va hisobot oyi bir-biriga mos emas.")
        return self

    def period(self, now: datetime) -> calendar_date:
        if now.tzinfo is None:
            raise ValueError("Xabar vaqt zonasi bo‘lishi kerak.")
        value = self.month or (self.date[:7] if self.date else None)
        return (
            calendar_date.fromisoformat(value + "-01")
            if value
            else now.astimezone(TASHKENT).date().replace(day=1)
        )

    def transaction(self, now: datetime) -> "LedgerSpec":
        if (
            self.intent not in {"income", "expense"}
            or self.amount is None
            or self.category is None
            or not self.description
            or self.clarification is not None
        ):
            raise ValueError("Summa, kirim/chiqim va izohni bitta xabarda aniq ayting.")
        if self.currency != "UZS":
            raise ValueError("Bu versiyada faqat so‘mdagi kirim-chiqim qayd qilinadi.")
        today = now.astimezone(TASHKENT).date()
        period = self.period(now)
        occurred = (
            calendar_date.fromisoformat(self.date) if self.date else (None if self.month else today)
        )
        if period > today.replace(day=1) or (occurred is not None and occurred > today):
            raise ValueError("Faqat amalga oshgan kirim yoki chiqimni qayd eting; sana kelajakda.")
        if self.intent == "expense" and self.category in {"oylik", "boshqa_kirim"}:
            raise ValueError("Chiqim kategoriyasi noto‘g‘ri. Xabarni aniqroq qayta ayting.")
        return LedgerSpec(
            self.intent, self.amount, self.category, self.description, period, occurred
        )


@dataclass(frozen=True, slots=True)
class LedgerSpec:
    kind: str
    amount: int
    category: str
    description: str
    period: calendar_date
    occurred_on: calendar_date | None


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: int
    kind: str
    amount: int
    category: str
    description: str
    period: calendar_date
    occurred_on: calendar_date | None
    cancelled: bool


@dataclass(frozen=True, slots=True)
class LedgerSummary:
    month: calendar_date
    income: int
    expense: int
    salary: int
    opening_balance: int

    @property
    def closing_balance(self) -> int:
        return self.opening_balance + self.income - self.expense


def format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so‘m"
