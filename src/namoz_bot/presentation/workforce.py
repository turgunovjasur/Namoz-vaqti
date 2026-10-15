"""Persistent menu plus private voice/text input and task-bound callbacks."""

import asyncio
from datetime import UTC, datetime
from io import BytesIO

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.voice_approval import VoiceApproval
from namoz_bot.application.voice_reminders import MAX_VOICE_BYTES, MAX_VOICE_SECONDS
from namoz_bot.application.workforce.assistant import AssistantService
from namoz_bot.domain.workforce.tasks import TaskConflict, TaskMessage
from namoz_bot.infrastructure.telegram import task_markup
from namoz_bot.presentation.handlers import HandlerServices, handle_start
from namoz_bot.presentation.keyboards import HELP_LABEL, build_main_menu
from namoz_bot.presentation.main_agent import agent_context
from namoz_bot.presentation.reminder_panel import APPEND_RESULTS, KEEP_MAIN_MENU
from namoz_bot.presentation.result_messages import VOICE_HELP
from namoz_bot.presentation.voice_conversation import (
    ConversationInputFilter,
    send_output,
)


class WorkforceController:
    def __init__(self, assistant: AssistantService, legacy: MainAgent):
        self.assistant, self.legacy = assistant, legacy

    async def _send(self, message: Message, state: FSMContext, reply: TaskMessage) -> None:
        await state.clear()
        await state.update_data(
            {KEEP_MAIN_MENU: True, APPEND_RESULTS: True, "hidden_menu_mode": True}
        )
        await message.answer("Yordamchi", reply_markup=build_main_menu(), parse_mode=None)
        await message.answer(reply.text, reply_markup=task_markup(reply), parse_mode=None)

    async def start(
        self, message: Message, state: FSMContext, handler_services: HandlerServices
    ) -> None:
        await handle_start(message, handler_services, state)

    async def help(self, message: Message, state: FSMContext) -> None:
        await self._send(message, state, TaskMessage(text=VOICE_HELP))

    async def receive(
        self, message: Message, state: FSMContext, handler_services: HandlerServices
    ) -> None:
        context = await agent_context(message, handler_services)
        request_id = f"wf:{context.bot_id}:m:{message.message_id}"
        # Old protocol drafts remain readable and execute through their original bridge.
        if (
            message.text
            and message.text.lower() in {"/resume", "davom et"}
            and await self.legacy.has_pending(context.user_id, datetime.now(UTC))
        ):
            await send_output(
                message, state, await self.legacy.resume(context=context, request_id=request_id)
            )
            return
        if message.text and message.text.lower() in {"/resume", "davom et"}:
            await self._send(
                message, state, await self.assistant.receive(context, request_id, text="/resume")
            )
            return
        if message.text == "/cancel" and await self.legacy.has_pending(
            context.user_id, datetime.now(UTC)
        ):
            pending = await self.legacy.store.get_session(context.user_id, datetime.now(UTC))
            assert pending is not None
            await send_output(
                message,
                state,
                await self.legacy.cancel(
                    context=context,
                    request_id=request_id,
                    operation_id=pending.operation_id,
                    revision=pending.revision,
                ),
            )
            return
        if message.text == "/cancel":
            await self.assistant.tasks.invalidate(context, questions=True)
            await self._send(message, state, TaskMessage(text="❌ Qoralama bekor qilindi."))
            return
        if message.text == "/menu":
            await handle_start(message, handler_services, state)
            return
        legacy_pending = await self.legacy.has_pending(context.user_id, datetime.now(UTC))
        if legacy_pending and message.text and not message.text.startswith("/"):
            await send_output(
                message,
                state,
                await self.legacy.respond(
                    context=context, request_id=request_id, text=message.text
                ),
            )
            return
        if await self.assistant.tasks.find_input(context, request_id):
            await self._send(
                message, state, await self.assistant.receive(context, request_id, text=message.text)
            )
            return
        await self.assistant.tasks.invalidate(context)
        if await self.legacy.has_pending(context.user_id, datetime.now(UTC)):
            await VoiceApproval(self.legacy).invalidate_input(
                context=context, request_id=request_id + ":retire"
            )
        if message.voice and (
            message.voice.duration > MAX_VOICE_SECONDS
            or (message.voice.file_size or 0) > MAX_VOICE_BYTES
        ):
            await self._send(
                message, state, TaskMessage(text="2 daqiqagacha va 5 MB dan kichik ovoz yuboring.")
            )
            return
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
                await self._send(
                    message,
                    state,
                    TaskMessage(text="Ovozni yuklab bo‘lmadi. Oldingi tasdiq bekor qilindi."),
                )
                return
        if legacy_pending and audio is not None:
            await send_output(
                message,
                state,
                await VoiceApproval(self.legacy).preview(
                    context=context,
                    request_id=request_id,
                    audio=audio,
                    mime_type=message.voice.mime_type or "audio/ogg"
                    if message.voice
                    else "audio/ogg",
                ),
            )
            return
        reply = await self.assistant.receive(
            context,
            request_id,
            text=message.text if audio is None else None,
            audio=audio,
            mime_type=(message.voice.mime_type or "audio/ogg") if message.voice else "audio/ogg",
        )
        await self._send(message, state, reply)

    async def callback(
        self, callback: CallbackQuery, state: FSMContext, handler_services: HandlerServices
    ) -> None:
        if (
            not isinstance(callback.message, Message)
            or callback.message.chat.id != callback.from_user.id
        ):
            await callback.answer("Bu tasdiq sizga tegishli emas.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[2].isdigit() or parts[3] not in {"y", "n"}:
            await callback.answer("Bu tasdiq eskirgan.", show_alert=True)
            return
        source = callback.message.model_copy(
            update={"from_user": callback.from_user, "date": datetime.now(UTC)}
        )
        context = await agent_context(source, handler_services)
        if parts[0] == "wff":
            try:
                reply = await self.assistant.feedback.rate(
                    context=context,
                    request_id=f"wff:{context.bot_id}:{callback.id}",
                    task_id=parts[1],
                    revision=int(parts[2]),
                    accepted=parts[3] == "y",
                )
            except TaskConflict:
                reply = TaskMessage(text="Bu natija kartasi eskirgan yoki sizga tegishli emas.")
        else:
            reply = await self.assistant.approve(
                context,
                f"wf:{context.bot_id}:c:{callback.id}",
                parts[1],
                int(parts[2]),
                parts[3] == "y",
            )
        await callback.answer()
        await self._send(callback.message, state, reply)


def build_workforce_router(assistant: AssistantService, legacy: MainAgent) -> Router:
    controller = WorkforceController(assistant, legacy)
    router = Router(name="workforce")
    private = F.chat.type == "private"
    router.message.register(controller.start, CommandStart(), private)
    router.message.register(controller.help, Command("help"), private)
    router.message.register(controller.help, F.text == HELP_LABEL, private)
    router.message.register(
        controller.receive, private, F.voice | F.text, ConversationInputFilter()
    )
    router.callback_query.register(
        controller.callback, F.data.startswith("wf:") | F.data.startswith("wff:")
    )
    return router
