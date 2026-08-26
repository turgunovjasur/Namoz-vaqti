"""Reusable Telegram keyboards."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from namoz_bot.domain.regions import list_region_groups, list_regions

TODAY_LABEL = "📅 Bugungi jadval"
REGION_LABEL = "📍 Hududni o‘zgartirish"
HELP_LABEL = "ℹ️ Yordam"
DISABLE_LABEL = "🔕 Xabarlarni o‘chirish"
ENABLE_LABEL = "🔔 Xabarlarni yoqish"


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


def build_main_menu(*, is_active: bool) -> ReplyKeyboardMarkup:
    """Build the persistent main menu for current subscription state."""

    toggle_label = DISABLE_LABEL if is_active else ENABLE_LABEL
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TODAY_LABEL), KeyboardButton(text=REGION_LABEL)],
            [KeyboardButton(text=toggle_label)],
            [KeyboardButton(text=HELP_LABEL)],
        ],
        resize_keyboard=True,
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
