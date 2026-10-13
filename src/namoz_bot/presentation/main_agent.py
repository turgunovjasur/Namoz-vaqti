"""One conversational entry point with deterministic, service-backed responses."""

import asyncio
from datetime import UTC, date, datetime
from io import BytesIO
from typing import cast

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pydantic import JsonValue

from namoz_bot.application.agent_adapters import HELP_TEXT
from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.voice_reminders import MAX_VOICE_BYTES, MAX_VOICE_SECONDS
from namoz_bot.domain.accounting import CATEGORY_LABELS, LedgerSummary, format_money
from namoz_bot.domain.agent_protocol import AgentContext, AgentResult
from namoz_bot.domain.models import PrayerKey
from namoz_bot.domain.reminders import ReminderSpec, parse_time
from namoz_bot.presentation.accounting import AccountingStates, _button, _keyboard, _summary_text
from namoz_bot.presentation.handlers import (
    HandlerServices,
    handle_offsets,
    handle_settings,
    handle_start,
)
from namoz_bot.presentation.keyboards import (
    ACCOUNTING_LABEL,
    ADD_LABEL,
    DAILY_SCHEDULE_LABEL,
    HELP_LABEL,
    HOME_LABEL,
    LIST_LABEL,
    NASIHAT_LABEL,
    OFFSETS_LABEL,
    PRAYER_LABELS,
    PRAYER_MENU_LABEL,
    REGION_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    RELIGIOUS_REMINDER_LABEL,
    REMINDERS_LABEL,
    SETTINGS_LABEL,
    TODAY_LABEL,
    TODAY_REMINDERS_LABEL,
)
from namoz_bot.presentation.religious_settings import show_interval
from namoz_bot.presentation.reminder_panel import KEEP_MAIN_MENU, delete_input, render_panel
from namoz_bot.presentation.reminders import _show_list
from namoz_bot.presentation.settings import show_daily, show_settings

NAVIGATION = {
    ACCOUNTING_LABEL,
    ADD_LABEL,
    DAILY_SCHEDULE_LABEL,
    HELP_LABEL,
    HOME_LABEL,
    LIST_LABEL,
    NASIHAT_LABEL,
    OFFSETS_LABEL,
    PRAYER_MENU_LABEL,
    REGION_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    RELIGIOUS_REMINDER_LABEL,
    REMINDERS_LABEL,
    SETTINGS_LABEL,
    TODAY_LABEL,
    TODAY_REMINDERS_LABEL,
}
MENU_MODE_KEY = "hidden_menu_mode"


def legacy_menu_input(message: Message, raw_state: str | None) -> bool:
    """Only menu navigation and active manual steps bypass the conversation."""
    if message.voice or not message.text or message.text == HELP_LABEL:
        return False
    text = message.text
    command = text.split()[0].split("@")[0] if text.strip() else ""
    return (
        text in NAVIGATION
        or (raw_state is not None and not text.startswith("/"))
        or command in {"/today", "/settings", "/offsets"}
    )


async def agent_context(message: Message, services: HandlerServices) -> AgentContext:
    assert message.from_user is not None and message.bot is not None
    user = (await services.subscriptions.start(message.from_user.id, message.chat.id)).subscription
    assert user.id is not None
    return AgentContext(
        bot_id=message.bot.id,
        telegram_user_id=message.from_user.id,
        chat_id=message.chat.id,
        user_id=user.id,
        message_time=message.date,
        region_code=user.region_code,
        offsets=user.offsets,
        language=message.from_user.language_code or "uz",
    )


class AgentMessageFilter(BaseFilter):
    def __init__(self, agent: MainAgent | None):
        self.agent = agent

    async def __call__(self, message: Message, state: FSMContext) -> bool:
        if self.agent is None or message.chat.type != "private" or message.from_user is None:
            return False
        if message.text and (message.text.startswith("/") or message.text in NAVIGATION):
            return False
        if not message.text and not message.voice:
            return False
        # Manual time/calendar/description inputs keep their existing dialog semantics.
        return await state.get_state() in {None, AccountingStates.active.state}


def _agent_button(result: AgentResult, action: str, label: str) -> InlineKeyboardButton:
    data = f"ag:{result.operation_id}:{result.data.get('revision', 0)}:{action}"
    return InlineKeyboardButton(text=label, callback_data=data)


async def render_agent_result(message: Message, state: FSMContext, result: AgentResult) -> None:
    data = result.data
    markup = None
    if result.status == "needs_input":
        text = result.question or "Xabarni aniqlashtiring."
    elif result.status == "needs_confirmation":
        draft = cast(dict[str, JsonValue], data["draft"])
        schedule = ReminderSpec(
            str(draft["text"]),
            parse_time(str(draft["time"])),
            str(draft["kind"]),
            date.fromisoformat(str(draft["date"])) if draft.get("date") else None,
            tuple(cast(list[int], draft.get("weekdays", []))),
        ).schedule_label()
        text = (
            f"📝 {draft.get('text')}\n🕒 {draft.get('time')} · Toshkent\n"
            f"📅 {schedule}\n\nSaqlashni tasdiqlang."
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [_agent_button(result, "save", "✅ Saqlash")],
                [_agent_button(result, "cancel", "❌ Bekor qilish")],
            ]
        )
    elif result.status == "error":
        text = {
            "no_active_task": "Tugallanmagan vazifa yo‘q.\n\n" + HELP_TEXT,
            "stale_operation": "Bu tasdiqlash eskirgan. «Davom et» deb joriy vazifani oching.",
            "voice_cooldown": "Yangi ovozli xabar uchun biroz kuting.",
            "invalid_input": "Ma’lumotlar mos kelmadi. Aniqlashtirib qayta yuboring.",
        }.get(
            result.error_code or "",
            "Xabarni qayta ishlay olmadim. Birozdan keyin qayta yuboring "
            "yoki menyudan foydalaning.",
        )
    elif result.status == "cancelled":
        text = str(data.get("text") or "Bu vazifa yakunlangan yoki bekor qilingan.")
    elif result.domain == "accounting" and result.status == "done":
        assert message.from_user is not None
        markup = _keyboard(message.from_user.id)
        await state.set_state(AccountingStates.active)
        if result.action in {"income", "expense"}:
            if data.get("cancelled"):
                text = "↩️ Bu yozuv bekor qilingan. Qayta hisobga qo‘shilmadi."
            else:
                text = (
                    "✅ Kirim qayd etildi" if result.action == "income" else "✅ Chiqim qayd etildi"
                )
                text += f"\n\n{format_money(int(str(data['amount'])))}\n{data['description']}"
                markup.inline_keyboard.insert(
                    0,
                    [
                        _button(
                            message.from_user.id,
                            "↩️ Yozuvni bekor qilish",
                            "undo",
                            str(data["entry_id"]),
                        )
                    ],
                )
            text += f"\n\nJoriy balans: {format_money(int(str(data['balance'])))}"
        elif result.action == "balance":
            text = f"💳 Joriy balans: {format_money(int(str(data['balance'])))}"
        elif result.action == "report":
            summary = LedgerSummary(
                date.fromisoformat(str(data["month"])),
                int(str(data["income"])),
                int(str(data["expense"])),
                int(str(data["salary"])),
                int(str(data["opening_balance"])),
            )
            text = _summary_text(summary, str(data.get("report_type", "summary")))
        else:
            text = "📒 Kirim-chiqim tarixi\n\n"
            entries = cast(list[dict[str, JsonValue]], data.get("entries", []))
            for entry in entries:
                text += (
                    f"#{entry['id']} · {entry['kind']} · "
                    f"{format_money(int(str(entry['amount'])))}\n"
                    f"{entry['description']} · {CATEGORY_LABELS[str(entry['category'])]}"
                    + (" · Bekor qilingan" if entry.get("cancelled") else "")
                    + "\n\n"
                )
                if not entry.get("cancelled"):
                    markup.inline_keyboard.insert(
                        0,
                        [
                            _button(
                                message.from_user.id,
                                f"↩️ #{entry['id']} ni bekor qilish",
                                "undo",
                                str(entry["id"]),
                            )
                        ],
                    )
            if not entries:
                text += "Hozircha yozuvlar yo‘q."
            if data.get("more"):
                markup.inline_keyboard.insert(
                    0,
                    [
                        _button(
                            message.from_user.id,
                            "Keyingi ➡️",
                            "history",
                            str(int(str(data.get("page", 0))) + 1),
                        )
                    ],
                )
    elif result.domain == "prayer" and data.get("prayer"):
        text = (
            f"🕌 {PRAYER_LABELS[cast(PrayerKey, data['prayer'])]}: {data['time']}\n"
            f"📍 {data['region']} · {data['date']}\nManba: namoz-vaqti.uz"
        )
    elif result.domain == "reminder" and result.action == "create" and result.status == "done":
        text = (
            f"✅ Eslatma saqlandi.\n\n📝 {data['text']}\n🕒 {data['time']}\n📅 {data['schedule']}"
        )
    elif result.domain == "reminder" and result.action == "list":
        text = "📋 Eslatmalar\n\n"
        entries = cast(list[dict[str, JsonValue]], data.get("entries", []))
        text += "\n\n".join(f"{e['time']} · {e['text']}\n{e['schedule']}" for e in entries)
        if not entries:
            text += "Hozircha eslatmalar yo‘q."
    else:
        text = str(data.get("text") or HELP_TEXT)
    await state.update_data({KEEP_MAIN_MENU: True})
    await render_panel(message, state, text, markup)


async def _navigate(
    message: Message,
    state: FSMContext,
    output: AgentResult,
    services: HandlerServices,
    reminders: ReminderService,
) -> bool:
    if output.status == "done" and output.domain == "reminder" and output.action == "list":
        assert message.from_user is not None
        await state.update_data({KEEP_MAIN_MENU: True})
        await _show_list(
            message,
            state,
            message.from_user.id,
            int(str(output.data.get("page", 0))),
            services,
            reminders,
            today=bool(output.data.get("today", False)),
        )
        return True
    view = output.data.get("view")
    if output.status != "done" or not view:
        return False
    if view == "region":
        await handle_settings(message, services)
    elif view == "offsets":
        await handle_offsets(message, services)
    elif view == "interval":
        await show_interval(message, services, state)
    elif view == "daily":
        await show_daily(message, state, services)
    elif view == "reminder_delete":
        assert message.from_user is not None
        await _show_list(
            message, state, message.from_user.id, 0, services, reminders, deleting=True
        )
    else:
        await show_settings(message, state)
    return True


async def receive_agent_message(
    message: Message,
    state: FSMContext,
    handler_services: HandlerServices,
    main_agent: MainAgent,
    reminder_service: ReminderService,
) -> None:
    if message.voice and (
        message.voice.duration > MAX_VOICE_SECONDS
        or (message.voice.file_size or 0) > MAX_VOICE_BYTES
    ):
        await message.answer("2 daqiqagacha va 5 MB dan kichik qisqa ovoz yuboring.")
        return
    progress = await message.answer("Xabaringiz tahlil qilinmoqda…")
    try:
        context = await agent_context(message, handler_services)
        audio = None
        if message.voice:
            assert message.bot is not None
            buffer = BytesIO()
            await asyncio.wait_for(
                message.bot.download(message.voice.file_id, destination=buffer), 20
            )
            audio = buffer.getvalue()
        output = await main_agent.respond(
            context=context,
            request_id=f"{context.bot_id}:{message.chat.id}:m:{message.message_id}",
            text=message.text if audio is None else None,
            audio=audio,
            mime_type=(message.voice.mime_type or "audio/ogg") if message.voice else "audio/ogg",
        )
    except (TelegramAPIError, TimeoutError, OSError):
        await message.answer("Ovozni yuklab bo‘lmadi. Qayta yuboring.")
        return
    finally:
        await delete_input(progress)
    if not await _navigate(message, state, output, handler_services, reminder_service):
        await render_agent_result(message, state, output)


async def agent_start(
    message: Message,
    state: FSMContext,
    handler_services: HandlerServices,
    main_agent: MainAgent,
) -> None:
    await handle_start(message, handler_services, state)
    await message.answer(HELP_TEXT)
    context = await agent_context(message, handler_services)
    if await main_agent.has_pending(context.user_id, datetime.now(UTC)):
        output = await main_agent.resume(context=context, request_id=f"start:{message.message_id}")
        await render_agent_result(message, state, output)


async def agent_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    main_agent: MainAgent | None = None,
) -> None:
    message = callback.message
    parts = (callback.data or "").split(":")
    if (
        main_agent is None
        or not isinstance(message, Message)
        or message.chat.type != "private"
        or message.chat.id != callback.from_user.id
        or len(parts) != 4
        or not parts[2].isdigit()
        or len(parts[1]) != 32
    ):
        await callback.answer("Bu tasdiqlash sizga tegishli emas yoki eskirgan.", show_alert=True)
        return
    # Telegram callback.message belongs to the bot, not the human; use authenticated sender.
    input_message = message.model_copy(
        update={"from_user": callback.from_user, "date": datetime.now(UTC)}
    )
    context = await agent_context(input_message, handler_services)
    kwargs = {
        "context": context,
        "request_id": f"{context.bot_id}:c:{callback.id}",
        "operation_id": parts[1],
        "revision": int(parts[2]),
    }
    if parts[3] == "save":
        output = await main_agent.confirm(
            context=context,
            request_id=str(kwargs["request_id"]),
            operation_id=parts[1],
            revision=int(parts[2]),
        )
    elif parts[3] == "cancel":
        output = await main_agent.cancel(
            context=context,
            request_id=str(kwargs["request_id"]),
            operation_id=parts[1],
            revision=int(parts[2]),
        )
    else:
        await callback.answer("Amal noto‘g‘ri.")
        return
    if output.status == "error":
        await callback.answer("Bu tasdiqlash eskirgan. «Davom et» deb yozing.", show_alert=True)
    else:
        await render_agent_result(input_message, state, output)
        await callback.answer()


def build_main_agent_router(main_agent: MainAgent | None = None) -> Router:
    if main_agent is not None and main_agent.voice_first:
        from namoz_bot.presentation.voice_conversation import build_voice_conversation_router
        return build_voice_conversation_router(main_agent)
    router = Router(name="main-agent")
    if main_agent is not None:
        router.message.register(agent_start, CommandStart(), F.chat.type == "private")
    router.message.register(receive_agent_message, AgentMessageFilter(main_agent))
    router.callback_query.register(agent_callback, F.data.startswith("ag:"))
    return router
