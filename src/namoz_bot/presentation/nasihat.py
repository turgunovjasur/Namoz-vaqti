"""Independent nasihat section using the existing book and interval services."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from namoz_bot.presentation.handlers import handle_religious_reminder
from namoz_bot.presentation.keyboards import (
    NASIHAT_LABEL,
    RELIGIOUS_REMINDER_LABEL,
    build_nasihat_menu,
)


async def show_nasihat(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📖 Nasihat. Kitobdan nasihat oling yoki avtomatik yuborish oralig‘ini sozlang:",
        reply_markup=build_nasihat_menu(),
    )


def build_nasihat_router() -> Router:
    router = Router(name="nasihat")
    router.message.filter(F.chat.type == "private")
    router.message.register(show_nasihat, F.text == NASIHAT_LABEL)
    # Retain the old action label so previously displayed keyboards remain usable.
    router.message.register(handle_religious_reminder, F.text == RELIGIOUS_REMINDER_LABEL)
    return router
