"""Month navigation and permission-filtered finance controls."""

from datetime import date, datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from namoz_bot.domain.accounting import LedgerEntry
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.presentation.agent_menu_context import menu_allows
from namoz_bot.presentation.reminder_keyboards import MONTHS

MONTH_KEY = "accounting_month"


def current_month() -> date:
    return datetime.now(TASHKENT).date().replace(day=1)


def month_label(month: date) -> str:
    return f"{MONTHS[month.month - 1]} {month.year}"


def button(owner: int, text: str, action: str, value: str = "-") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=f"acct:{owner}:{action}:{value}")


def keyboard(
    owner: int, entry: LedgerEntry | None = None, month: date | None = None
) -> InlineKeyboardMarkup:
    month = month or current_month()
    rows = []
    if entry is not None and not entry.cancelled and menu_allows("finance.undo"):
        rows.append([button(owner, "↩️ Yozuvni bekor qilish", "undo", str(entry.id))])
    if menu_allows("finance.report") or menu_allows("finance.history"):
        nav = []
        if month.year > 1 or month.month > 1:
            previous = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)
            nav.append(button(owner, "◀️ Oldingi oy", "month", previous.isoformat()))
        nav.append(button(owner, "📅 Oy tanlash", "year", str(month.year)))
        if month < current_month():
            following = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
            nav.append(button(owner, "Keyingi oy ▶️", "month", following.isoformat()))
        rows.append(nav)
    for actions in (
        (
            ("finance.income", "➕ Kirim yozish", "income"),
            ("finance.expense", "\N{HEAVY MINUS SIGN} Xarajat yozish", "expense"),
        ),
        (
            ("finance.report", "📊 Oy hisoboti", "summary"),
            ("finance.history", "📒 Shu oy tarixi", "history"),
        ),
        (("finance.balance", "💳 Umumiy balans", "balance"),),
    ):
        row = [
            button(owner, label, action, "0" if action == "history" else "-")
            for cap, label, action in actions
            if menu_allows(cap)
        ]
        if row:
            rows.append(row)
    rows.append([button(owner, "⬅️ Asosiy menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def month_picker(owner: int, year: int) -> InlineKeyboardMarkup:
    today = current_month()
    if not 1 <= year <= today.year:
        raise ValueError("Yil noto‘g‘ri")
    months = [
        button(owner, MONTHS[m - 1], "month", date(year, m, 1).isoformat())
        for m in range(1, 13)
        if date(year, m, 1) <= today
    ]
    rows = [months[i : i + 3] for i in range(0, len(months), 3)]
    years = []
    if year > 1:
        years.append(button(owner, f"◀️ {year - 1}", "year", str(year - 1)))
    if year < today.year:
        years.append(button(owner, f"{year + 1} ▶️", "year", str(year + 1)))
    if years:
        rows.append(years)
    rows.append([button(owner, "📅 Joriy oy", "month", today.isoformat())])
    rows.append([button(owner, "⬅️ Asosiy menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
