"""Reusable Telegram keyboards."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from namoz_bot.domain.models import PrayerKey
from namoz_bot.domain.regions import list_region_groups, list_regions

PROFILE_LABEL = "👤 Profil"
_visible_roles: ContextVar[frozenset[str] | None] = ContextVar("visible_menu_roles", default=None)


@contextmanager
def menu_visibility(roles: frozenset[str]) -> Iterator[None]:
    token = _visible_roles.set(roles)
    try:
        yield
    finally:
        _visible_roles.reset(token)


TODAY_LABEL = "📅 Bugungi jadval"
REGION_LABEL = "📍 Hududni o‘zgartirish"
HELP_LABEL = "ℹ️ Yordam"
OFFSETS_LABEL = "🕌 Masjidga moslash"
RELIGIOUS_REMINDER_LABEL = "📖 Diniy eslatma"
NASIHAT_LABEL = "📖 Nasihat"
RELIGIOUS_INTERVAL_LABEL = "⚙️ Nasihat intervali"
SETTINGS_LABEL = "⚙️ Sozlamalar"
DAILY_SCHEDULE_LABEL = "⚙️ Sozlash"

PRAYER_LABELS: dict[PrayerKey, str] = {
    "bomdod": "Bomdod",
    "quyosh": "Quyosh",
    "peshin": "Peshin",
    "asr": "Asr",
    "shom": "Shom",
    "xufton": "Xufton",
}


def format_offset_value(value: int) -> str:
    """Render one minute difference consistently across settings views."""

    if value > 0:
        return f"+{value} daqiqa"
    if value < 0:
        return f"\N{MINUS SIGN}{abs(value)} daqiqa"
    return "0 daqiqa"


def build_offsets_keyboard() -> InlineKeyboardMarkup:
    """Build the six-prayer personal offset selector."""

    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"offset:{prayer}",
        )
        for prayer, label in PRAYER_LABELS.items()
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_offset_adjustment_keyboard(
    prayer: PrayerKey,
    value: int,
) -> InlineKeyboardMarkup:
    """Build one-minute controls for a selected prayer."""

    if prayer not in PRAYER_LABELS or not -30 <= value <= 30:
        raise ValueError("Offset boshqaruvi noto‘g‘ri")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\N{MINUS SIGN}1",
                    callback_data=f"offset-change:{prayer}:-1",
                ),
                InlineKeyboardButton(
                    text="0",
                    callback_data=f"offset-change:{prayer}:0",
                ),
                InlineKeyboardButton(
                    text="+1",
                    callback_data=f"offset-change:{prayer}:1",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Taqvimga qaytish",
                    callback_data="offset-schedule",
                )
            ],
        ]
    )


def build_region_group_keyboard() -> InlineKeyboardMarkup:
    """Build the first-level Uzbekistan geographic group selector."""

    groups = list_region_groups()
    rows: list[list[InlineKeyboardButton]] = []
    for index in range(0, len(groups), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=group.display_name,
                    callback_data=f"region-group:{group.code}",
                )
                for group in groups[index : index + 2]
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_prayer_menu() -> ReplyKeyboardMarkup:
    """Build the prayer section menu."""

    from namoz_bot.presentation.agent_menu_context import selected_role

    if selected_role() is not None:
        return build_agent_actions_menu()
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TODAY_LABEL), KeyboardButton(text=REGION_LABEL)],
            [KeyboardButton(text=OFFSETS_LABEL), KeyboardButton(text=DAILY_SCHEDULE_LABEL)],
            [KeyboardButton(text=HOME_LABEL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )


def build_region_keyboard(*, group_code: str) -> InlineKeyboardMarkup:
    """Build a clear second-level selector for one geographic group."""

    rows = [
        [
            InlineKeyboardButton(
                text=region.display_name,
                callback_data=f"region:{region.code}",
            )
        ]
        for region in list_regions(group_code=group_code)
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Viloyatlar", callback_data="region-groups")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


QORI_LABEL = "📖 Qori"
PRAYER_MENU_LABEL = "🕌 Namoz vaqti"
REMINDERS_LABEL = "🔔 Eslatmalar"
LIST_LABEL = "📋 Eslatma ro‘yxati"
TODAY_REMINDERS_LABEL = "📅 Bugungi eslatmalar"
ADD_LABEL = "➕ Eslatma qo‘shish"
HOME_LABEL = "⬅️ Asosiy menyu"
ACCOUNTING_LABEL = "💰 Kirim-chiqim"


def build_agent_actions_menu() -> ReplyKeyboardMarkup:
    from namoz_bot.presentation.agent_menu_context import action_labels

    labels = list(action_labels())
    rows = [
        [KeyboardButton(text=label) for label in labels[i : i + 2]]
        for i in range(0, len(labels), 2)
    ]
    rows.append([KeyboardButton(text=HOME_LABEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def build_main_menu() -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    from namoz_bot.presentation.agent_menu_context import agent_label, menu_roles, show_qori

    agents = menu_roles()
    if agents is not None:
        labels = [agent_label(role) for role in agents]
        if show_qori():
            labels.append(QORI_LABEL)
        rows = [
            [KeyboardButton(text=label) for label in labels[i : i + 2]]
            for i in range(0, len(labels), 2)
        ]
        if not rows:
            return ReplyKeyboardRemove()
        return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)
    visible = _visible_roles.get()
    sections = [
        ("prayer", PRAYER_MENU_LABEL),
        ("nasihat", NASIHAT_LABEL),
        ("reminder", REMINDERS_LABEL),
        ("accounting", ACCOUNTING_LABEL),
    ]
    labels = [label for role, label in sections if visible is None or role in visible]
    rows = [
        [KeyboardButton(text=label) for label in labels[i : i + 2]]
        for i in range(0, len(labels), 2)
    ]
    if not rows:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        keyboard=rows, resize_keyboard=True, is_persistent=True, one_time_keyboard=False
    )


def build_voice_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=HELP_LABEL)]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )


def build_settings_menu() -> ReplyKeyboardMarkup:
    from namoz_bot.presentation.agent_menu_context import selected_role

    if selected_role() is not None:
        return build_agent_actions_menu()
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=DAILY_SCHEDULE_LABEL)],
            [KeyboardButton(text=HOME_LABEL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )


def build_nasihat_menu() -> ReplyKeyboardMarkup:
    from namoz_bot.presentation.agent_menu_context import selected_role

    if selected_role() is not None:
        return build_agent_actions_menu()
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RELIGIOUS_REMINDER_LABEL)],
            [KeyboardButton(text=RELIGIOUS_INTERVAL_LABEL)],
            [KeyboardButton(text=HOME_LABEL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )
