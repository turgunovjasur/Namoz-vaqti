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
    token: str,
    step: str,
    *,
    month: date | None = None,
    today: date | None = None,
    weekdays: tuple[int, ...] = (),
    hour: int | None = None,
    minute: int | None = None,
    time_view: str = "hour",
    minute_page: int = 0,
    kind: str | None = None,
    selected_date: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if step == "schedule":
        rows = [
            [button(token, f"✅ {label}" if value == kind else label, "kind", value)]
            for label, value in (
                ("📅 Sana tanlash", "once"),
                ("🔁 Har kuni", "daily"),
                ("📆 Har hafta", "weekly"),
            )
        ]
    elif step == "time":
        hour_label = f"{hour:02d}" if hour is not None else "—"
        minute_label = f"{minute:02d}" if minute is not None else "—"
        rows.append(
            [
                button(token, f"Soat: {hour_label}", "timeview", "hour"),
                button(token, f"Daqiqa: {minute_label}", "timeview", "minute"),
            ]
        )
        values = (
            range(24) if time_view == "hour" else range(minute_page * 30, minute_page * 30 + 30)
        )
        selected = hour if time_view == "hour" else minute
        choices = [
            button(
                token,
                f"✅ {value:02d}" if value == selected else f"{value:02d}",
                time_view,
                str(value),
            )
            for value in values
        ]
        rows.extend(choices[index : index + 6] for index in range(0, len(choices), 6))
        if time_view == "minute":
            rows.append(
                [button(token, "00–29", "minutes", "0"), button(token, "30–59", "minutes", "1")]
            )
    elif step == "weekday":
        days = [
            button(token, f"{'✅' if index in weekdays else '⬜'} {label}", "weekday", str(index))
            for index, label in enumerate(WEEKDAYS)
        ]
        rows = [days[index : index + 3] for index in range(0, len(days), 3)]
    elif step == "date":
        assert month is not None and today is not None
        rows.append([button(token, f"{MONTHS[month.month - 1]} {month.year}", "noop")])
        rows.append(
            [button(token, day, "noop") for day in ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")]
        )
        for week in calendar.monthcalendar(month.year, month.month):
            rows.append(
                [
                    button(
                        token,
                        f"✅ {day}"
                        if selected_date == date(month.year, month.month, day).isoformat()
                        else str(day),
                        "date",
                        date(month.year, month.month, day).isoformat(),
                    )
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
    if step == "confirm":
        rows.extend([[button(token, "✅ Saqlash", "save")], [button(token, "⬅️ Orqaga", "back")]])
    elif step == "weekday":
        rows.append([button(token, "⬅️ Orqaga", "back"), button(token, "✅ Tayyor", "done")])
    else:
        rows.append([button(token, "⬅️ Orqaga", "back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def page_keyboard(
    owner: int,
    page: int,
    has_more: bool,
    *,
    part: int = 0,
    parts: int = 1,
    deleting: bool = False,
) -> InlineKeyboardMarkup:
    row = []
    if part or page:
        previous_page, previous_part = (page, part - 1) if part else (page - 1, -1)
        row.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi", callback_data=f"remlist:{owner}:{previous_page}:{previous_part}"
            )
        )
    if part < parts - 1 or has_more:
        next_page, next_part = (page, part + 1) if part < parts - 1 else (page + 1, 0)
        row.append(
            InlineKeyboardButton(
                text="Keyingi ➡️", callback_data=f"remlist:{owner}:{next_page}:{next_part}"
            )
        )
    rows = [row] if row else []
    if not deleting:
        rows.append(
            [
                InlineKeyboardButton(text="➕ Qo‘shish", callback_data=f"remmenu:{owner}:add"),
                InlineKeyboardButton(
                    text="\N{HEAVY MINUS SIGN} O‘chirish", callback_data=f"remmenu:{owner}:delete"
                ),
            ]
        )
    action = "list" if deleting else "home"
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"remmenu:{owner}:{action}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_keyboard(token: str, reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label, callback_data=f"remdel:{token}:{action}:{reminder_id}"
                )
            ]
            for label, action in (("🗑 Ha, o‘chirish", "yes"), ("⬅️ Orqaga", "back"))
        ]
    )
