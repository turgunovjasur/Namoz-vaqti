"""Keep the reminder UI in one editable message per private chat."""

import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardRemove

logger = logging.getLogger(__name__)
PANEL_ID = "reminder_panel_id"


async def reset_draft(state: FSMContext) -> None:
    """Forget dialog fields while retaining the reusable UI message."""
    data = await state.get_data()
    retained = {PANEL_ID: data[PANEL_ID]} if data.get(PANEL_ID) is not None else {}
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
    if data.get(PANEL_ID) is not None:
        await _delete(message, int(data[PANEL_ID]))


async def render_panel(
    message: Message, state: FSMContext, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    assert message.bot is not None
    panel_id = (await state.get_data()).get(PANEL_ID)
    if panel_id is not None:
        try:
            await message.bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=int(panel_id),
                reply_markup=markup,
                parse_mode=None,
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
    # Telegram requires a separate send to remove a reply keyboard. Keep only
    # the inline panel in chat; the removal message must never become the panel.
    removal = await message.answer("🔔 Eslatmalar", reply_markup=ReplyKeyboardRemove())
    try:
        sent = await message.answer(text, reply_markup=markup, parse_mode=None)
        await state.update_data({PANEL_ID: sent.message_id})
    finally:
        await _delete(message, removal.message_id)
