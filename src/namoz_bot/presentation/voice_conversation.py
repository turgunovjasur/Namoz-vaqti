"""Visible menus, main-agent voice approvals and fresh text result messages."""

import asyncio
from datetime import UTC, datetime
from io import BytesIO

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.voice_approval import VoiceApproval
from namoz_bot.application.voice_reminders import MAX_VOICE_BYTES, MAX_VOICE_SECONDS
from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.presentation.handlers import HandlerServices, handle_start
from namoz_bot.presentation.keyboards import HELP_LABEL, build_main_menu
from namoz_bot.presentation.main_agent import MENU_MODE_KEY, agent_context, legacy_menu_input
from namoz_bot.presentation.reminder_panel import discard_panel
from namoz_bot.presentation.result_messages import VOICE_HELP
from namoz_bot.presentation.result_messages import render_result as response_text
from namoz_bot.presentation.voice_approval import approval_buttons


async def send_text(message: Message, state: FSMContext, text: str) -> None:
    await discard_panel(message, state)
    await state.clear()
    await state.update_data({MENU_MODE_KEY: True})
    await message.answer(text, reply_markup=build_main_menu(), parse_mode=None)


async def send_output(message: Message, state: FSMContext, output: AgentResult) -> None:
    if output.status == "needs_confirmation":
        await send_text(message, state, "Buyruqni tekshiring va tasdiqlang.")
        await message.answer(
            response_text(output), reply_markup=approval_buttons(output), parse_mode=None
        )
    else:
        await send_text(message, state, response_text(output))


async def help_message(message: Message, state: FSMContext) -> None:
    await send_text(message, state, VOICE_HELP)


async def start_conversation(
    message: Message, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent
) -> None:
    context = await agent_context(message, handler_services)
    await send_text(message, state, VOICE_HELP)
    if await main_agent.has_pending(context.user_id, datetime.now(UTC)):
        output = await main_agent.resume(context=context, request_id=f"start:{message.message_id}")
        await send_output(message, state, output)


async def open_hidden_menu(
    message: Message, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent
) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    context = await agent_context(message, handler_services)
    if await main_agent.has_pending(context.user_id, datetime.now(UTC)):
        output = await main_agent.resume(context=context, request_id=f"menu:{message.message_id}")
        await send_output(message, state, output)
        return
    await handle_start(message, handler_services, state)
    await state.update_data({MENU_MODE_KEY: True})


async def receive_conversation(
    message: Message, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent
) -> None:
    if message.from_user is None or message.chat.id != message.from_user.id:
        return
    context = await agent_context(message, handler_services)
    request_id = f"{context.bot_id}:{message.chat.id}:m:{message.message_id}"
    if message.voice and (
        message.voice.duration > MAX_VOICE_SECONDS
        or (message.voice.file_size or 0) > MAX_VOICE_BYTES
    ):
        await VoiceApproval(main_agent).invalidate_input(context=context, request_id=request_id)
        await send_text(message, state, "2 daqiqagacha va 5 MB dan kichik ovoz yuboring.")
        return
    await discard_panel(message, state)
    await state.clear()
    audio = None
    if message.voice:
        buffer = BytesIO()
        try:
            assert message.bot is not None
            await asyncio.wait_for(
                message.bot.download(message.voice.file_id, destination=buffer), 20
            )
            audio = buffer.getvalue()
        except (TelegramAPIError, TimeoutError, OSError):
            await VoiceApproval(main_agent).invalidate_input(context=context, request_id=request_id)
            await send_text(message, state, "Ovozni yuklab bo‘lmadi. Qayta yuboring.")
            return
    text = message.text
    if text and text.startswith("/"):
        commands = {
            "/today": "Bugungi namoz jadvalini ko‘rsat",
            "/settings": "Sozlamalarni ko‘rsat",
            "/offsets": "Masjidga moslash farqlarini ko‘rsat",
            "/cancel": "Bekor qil",
            "/resume": "Davom et",
        }
        text = commands.get(text.split()[0].split("@")[0])
        if text is None:
            await help_message(message, state)
            return
    if audio is not None:
        assert message.voice is not None
        output = await VoiceApproval(main_agent).preview(
            context=context,
            request_id=request_id,
            audio=audio,
            mime_type=message.voice.mime_type or "audio/ogg",
        )
        await send_output(message, state, output)
        return
    output = await main_agent.respond(
        context=context,
        request_id=request_id,
        text=text if audio is None else None,
        audio=audio,
        mime_type=(message.voice.mime_type or "audio/ogg") if message.voice else "audio/ogg",
    )
    await send_output(message, state, output)


async def approve_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    main_agent: MainAgent,
) -> None:
    if (
        not isinstance(callback.message, Message)
        or callback.message.chat.id != callback.from_user.id
    ):
        await callback.answer("Bu tasdiq sizga tegishli emas.", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if (
        len(parts) != 4
        or parts[0] not in {"vr", "ag"}
        or not parts[2].isdigit()
        or parts[3] not in {"y", "n"}
    ):
        await callback.answer("Bu tasdiq eskirgan.", show_alert=True)
        return
    source = callback.message.model_copy(
        update={"from_user": callback.from_user, "date": datetime.now(UTC)}
    )
    context = await agent_context(source, handler_services)
    request_id = f"{context.bot_id}:{context.chat_id}:c:{callback.id}"
    if parts[0] == "vr":
        output = await VoiceApproval(main_agent).decide(
            context=context,
            request_id=request_id,
            operation_id=parts[1],
            revision=int(parts[2]),
            accept=parts[3] == "y",
        )
    else:
        method = main_agent.confirm if parts[3] == "y" else main_agent.cancel
        output = await method(
            context=context, request_id=request_id, operation_id=parts[1], revision=int(parts[2])
        )
    await callback.answer()
    if output.status != "error":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramAPIError:
            pass
    await send_output(callback.message, state, output)


async def retired_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Buyruqni ovoz bilan ayting.")
    if isinstance(callback.message, Message) and callback.message.chat.id == callback.from_user.id:
        await send_text(
            callback.message, state, "Endi buyruqlar ovoz orqali bajariladi. Kerakli ishni ayting."
        )


class ConversationInputFilter(BaseFilter):
    async def __call__(
        self, message: Message, raw_state: str | None = None, hidden_menu_mode: bool = False
    ) -> bool:
        return not hidden_menu_mode or not legacy_menu_input(message, raw_state)


class RetiredCallbackFilter(BaseFilter):
    async def __call__(self, callback: CallbackQuery, hidden_menu_mode: bool = False) -> bool:
        return not hidden_menu_mode or bool(callback.data and callback.data.startswith("ag:"))


def build_voice_conversation_router(main_agent: MainAgent) -> Router:
    router = Router(name="voice-conversation")
    private = F.chat.type == "private"
    router.message.register(start_conversation, CommandStart(), private)
    router.message.register(help_message, Command("help"), private)
    router.message.register(help_message, F.text == HELP_LABEL, private)
    router.message.register(open_hidden_menu, Command("menu"))
    router.message.register(
        receive_conversation, private, F.voice | F.text, ConversationInputFilter()
    )
    router.callback_query.register(
        approve_callback,
        F.message.chat.type == "private",
        F.data.startswith("vr:") | F.data.startswith("ag:"),
    )
    router.callback_query.register(
        retired_callback, F.message.chat.type == "private", RetiredCallbackFilter()
    )
    return router
