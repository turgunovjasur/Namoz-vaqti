"""Compact callbacks contain only an opaque card token and an action index."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def profile_keyboard(token: str, labels: list[str]) -> InlineKeyboardMarkup | None:
    if not labels:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"pf:{token}:{index}")]
            for index, label in enumerate(labels)
        ]
    )
