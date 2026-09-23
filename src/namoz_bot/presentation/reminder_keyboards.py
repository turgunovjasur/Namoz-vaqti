"""Calendar and dialog controls with per-prompt callback tokens."""

import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from namoz_bot.domain.reminders import WEEKDAYS

MONTHS = (
    "Yanvar",
    "Fevral",
    "Mart",
    "Aprel",
    "May",
    "Iyun",
    "Iyul",
    "Avgust",
    "Sentabr",
    "Oktabr",
    "Noyabr",
    "Dekabr",
)


def button(token: str, label: str, action: str, value: str = "-") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=f"rem:{token}:{action}:{value}")


def dialog_keyboard(
    token: str, step: str, *, month: date | None = None, today: date | None = None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if step == "schedule":
        rows = [
            [button(token, label, "kind", kind)]
            for label, kind in (
                ("📅 Sana tanlash", "once"),
                ("🔁 Har kuni", "daily"),
                ("📆 Har hafta", "weekly"),
            )
        ]
    elif step == "weekday":
        rows = [
            [button(token, label, "weekday", str(index))] for index, label in enumerate(WEEKDAYS)
        ]
    elif step == "date":
        assert month is not None and today is not None
        rows.append([button(token, f"{MONTHS[month.month - 1]} {month.year}", "noop")])
        rows.append(
            [button(token, day, "noop") for day in ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")]
        )
        for week in calendar.monthcalendar(month.year, month.month):
            rows.append(
                [
                    button(token, str(day), "date", date(month.year, month.month, day).isoformat())
                    if day and date(month.year, month.month, day) >= today
                    else button(token, "·", "noop")
                    for day in week
                ]
            )
        navigation = []
        if (month.year, month.month) > (today.year, today.month):
            previous = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)
            navigation.append(button(token, "⬅️ Oldingi oy", "month", previous.isoformat()))
        if month.year < min(today.year + 100, 9999):
            following = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
            navigation.append(button(token, "Keyingi oy ➡️", "month", following.isoformat()))
        if navigation:
            rows.append(navigation)
    elif step == "confirm":
        rows.append([button(token, "✅ Saqlash", "save")])
    rows.append([button(token, "⬅️ Orqaga", "back"), button(token, "❌ Bekor qilish", "cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def page_keyboard(owner: int, page: int, has_more: bool) -> InlineKeyboardMarkup:
    row = []
    if page:
        row.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"remlist:{owner}:{page - 1}")
        )
    if has_more:
        row.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"remlist:{owner}:{page + 1}")
        )
    return InlineKeyboardMarkup(inline_keyboard=[row] if row else [])
