"""Reusable Telegram keyboards."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from namoz_bot.domain.regions import list_regions

TODAY_LABEL = "📅 Bugungi jadval"
REGION_LABEL = "📍 Hududni o‘zgartirish"
HELP_LABEL = "ℹ️ Yordam"
DISABLE_LABEL = "🔕 Xabarlarni o‘chirish"
ENABLE_LABEL = "🔔 Xabarlarni yoqish"


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


def build_region_keyboard(*, page: int, page_size: int = 10) -> InlineKeyboardMarkup:
    """Build a bounded, paginated keyboard from the trusted catalog."""

    regions = list_regions()
    last_page = max(0, (len(regions) - 1) // page_size)
    current_page = min(max(page, 0), last_page)
    start = current_page * page_size
    end = min(start + page_size, len(regions))

    rows: list[list[InlineKeyboardButton]] = []
    for index in range(start, end, 2):
        row: list[InlineKeyboardButton] = []
        for item_index in range(index, min(index + 2, end)):
            row.append(
                InlineKeyboardButton(
                    text=regions[item_index].display_name,
                    callback_data=f"region:{current_page}:{item_index}",
                )
            )
        rows.append(row)

    navigation: list[InlineKeyboardButton] = []
    if current_page > 0:
        navigation.append(
            InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"regions:{current_page - 1}")
        )
    if current_page < last_page:
        navigation.append(
            InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"regions:{current_page + 1}")
        )
    if navigation:
        rows.append(navigation)

    return InlineKeyboardMarkup(inline_keyboard=rows)
