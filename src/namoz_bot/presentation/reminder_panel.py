"""Keep the reminder UI in one editable message per private chat."""

import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.utils.formatting import Text

from namoz_bot.presentation.keyboards import build_main_menu

logger = logging.getLogger(__name__)
PANEL_ID = "reminder_panel_id"
MAIN_ID = "main_menu_message_id"
KEEP_MAIN_MENU = "reminder_keep_main_menu"


async def reset_draft(state: FSMContext) -> None:
    """Forget dialog fields while retaining the reusable UI message."""
    data = await state.get_data()
    retained = {
        key: data[key] for key in (PANEL_ID, MAIN_ID, KEEP_MAIN_MENU) if data.get(key) is not None
    }
    await state.clear()
    await state.set_data(retained)


async def _delete(message: Message, message_id: int) -> None:
    assert message.bot is not None
    try:
        await message.bot.delete_message(message.chat.id, message_id)
    except TelegramAPIError as exc:
        # Cleanup must not prevent saving or navigating a reminder.
        logger.info("reminder_ui_cleanup_failed error=%s", type(exc).__name__)


async def delete_input(message: Message) -> None:
    """Remove only the current private-chat input consumed by this flow."""
    if message.chat.type == "private":
        await _delete(message, message.message_id)


async def discard_panel(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    for key in (PANEL_ID, MAIN_ID):
        if data.get(key) is not None:
            await _delete(message, int(data[key]))


async def show_main_menu(message: Message, state: FSMContext) -> None:
    await discard_panel(message, state)
    await state.clear()
    sent = await message.answer("Asosiy menyu. Bo‘limni tanlang:", reply_markup=build_main_menu())
    await state.update_data({MAIN_ID: sent.message_id})


async def render_panel(
    message: Message,
    state: FSMContext,
    text: str | Text,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    assert message.bot is not None
    rendered, entities = text.render() if isinstance(text, Text) else (text, [])
    data = await state.get_data()
    keep_menu = bool(data.get(KEEP_MAIN_MENU))
    if keep_menu and data.get(MAIN_ID) is None:
        main = await message.answer(
            "Asosiy menyu. Bo‘limni tanlang:", reply_markup=build_main_menu()
        )
        await state.update_data({MAIN_ID: main.message_id})
    elif not keep_menu and data.get(MAIN_ID) is not None:
        await _delete(message, int(data[MAIN_ID]))
        await state.update_data({MAIN_ID: None})
    panel_id = data.get(PANEL_ID)
    if panel_id is not None:
        try:
            await message.bot.edit_message_text(
                rendered,
                chat_id=message.chat.id,
                message_id=int(panel_id),
                reply_markup=markup,
                parse_mode=None,
                entities=entities,
            )
            return
        except TelegramBadRequest as exc:
            description = exc.message.lower()
            if "message is not modified" in description:
                return
            if not any(
                reason in description
                for reason in (
                    "message to edit not found",
                    "message can't be edited",
                    "message_id_invalid",
                )
            ):
                raise
            await _delete(message, int(panel_id))
    # Manual entry uses only the inline panel. Voice entry keeps the main menu
    # alongside it, including when rendering a fresh panel after deletion.
    removal = (
        None
        if keep_menu
        else await message.answer("🔔 Eslatmalar", reply_markup=ReplyKeyboardRemove())
    )
    try:
        sent = await message.answer(
            rendered, reply_markup=markup, parse_mode=None, entities=entities
        )
        await state.update_data({PANEL_ID: sent.message_id})
    finally:
        if removal is not None:
            await _delete(message, removal.message_id)
