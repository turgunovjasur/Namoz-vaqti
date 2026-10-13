"""One voice-driven conversation with text replies and a Help-only keyboard."""

import asyncio
from datetime import UTC, date, datetime
from io import BytesIO
from typing import cast

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from pydantic import JsonValue

from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.voice_reminders import MAX_VOICE_BYTES, MAX_VOICE_SECONDS
from namoz_bot.domain.accounting import format_money
from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.domain.models import PrayerKey
from namoz_bot.domain.reminders import ReminderSpec, parse_time
from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import HELP_LABEL, PRAYER_LABELS, build_voice_menu
from namoz_bot.presentation.main_agent import agent_context

VOICE_HELP = (
    "Ovozli xabar yuboring — kerakli bo‘limni o‘zim aniqlayman. Javoblar matnda keladi.\n\n"
    "🕌 «Bugun shom nechida?»\n"
    "📍 «Hududni Samarqand shahriga o‘zgartir»\n"
    "🕌 «Shom vaqtini 4 daqiqa keyinga sur»\n"
    "📖 «Kitobdan nasihat ber»\n"
    "📖 «Nasihat har 6 soatda kelsin» yoki «Avtomatik nasihatni o‘chir»\n"
    "🔔 «Ertaga ertalab 9 da uchrashuvni eslat»\n"
    "🔔 «Eslatmalarimni ko‘rsat», «Kitob eslatmasini o‘chir»\n"
    "💰 «120 mingga kiyim oldim», «Balansim qancha?»\n"
    "📊 «Shu oy qancha sarfladim?», «Yozuvlar tarixini ko‘rsat»\n"
    "↩️ «Oxirgi yozuvni bekor qil»\n"
    "⚙️ «Kunlik jadval ertalab 7 da kelsin»\n\n"
    "Tasdiq so‘ralsa «Ha, tasdiqlayman» deng. Vazifa uchun «Davom et» yoki «Bekor qil» deng.\n"
    "Matnli buyruq ham ishlaydi. Tugma bosish shart emas. Vaqtlar Toshkent vaqti bo‘yicha."
)


def response_text(output: AgentResult) -> str:
    data = output.data
    if output.status == "needs_input":
        return output.question or "Xabarni aniqlashtiring."
    if output.status == "needs_confirmation":
        if output.action == "create":
            draft = cast(dict[str, JsonValue], data["draft"])
            text = f"📝 {draft['text']}\n🕒 {draft['time']} · Toshkent\n"
            schedule = ReminderSpec(
                str(draft["text"]),
                parse_time(str(draft["time"])),
                str(draft["kind"]),
                date.fromisoformat(str(draft["date"])) if draft.get("date") else None,
                tuple(cast(list[int], draft.get("weekdays", []))),
            ).schedule_label()
            text += f"📅 {schedule}\n\nEslatmani saqlashni tasdiqlaysizmi?"
        else:
            verb = "o‘chirishni" if output.action == "delete" else "bekor qilishni"
            text = f"{data.get('summary')}\n\nShu yozuvni {verb} tasdiqlaysizmi?"
        return text + "\n«Ha, tasdiqlayman» yoki «Bekor qil» deng."
    if output.status == "error":
        return {
            "no_active_task": "Tugallanmagan vazifa yo‘q. Yangi buyruqni ovoz bilan ayting.",
            "stale_operation": "Bu tasdiq eskirgan. «Davom et» deb joriy vazifani so‘rang.",
            "invalid_input": "Ma’lumotlar mos kelmadi. Aniqlashtirib qayta ayting.",
        }.get(
            output.error_code or "", "Xabarni qayta ishlay olmadim. Birozdan keyin qayta yuboring."
        )
    if output.status == "cancelled":
        return str(data.get("text") or "Vazifa yakunlangan yoki bekor qilingan.")
    if output.domain == "prayer" and data.get("prayer"):
        return (
            f"🕌 {PRAYER_LABELS[cast(PrayerKey, data['prayer'])]}: {data['time']}\n"
            f"📍 {data['region']} · {data['date']}\nManba: namoz-vaqti.uz"
        )
    if output.domain == "reminder" and output.action == "create" and output.status == "done":
        return f"✅ Eslatma saqlandi.\n📝 {data['text']}\n🕒 {data['time']}\n📅 {data['schedule']}"
    if data.get("text"):
        return str(data["text"])
    if output.domain == "accounting":
        if output.action in {"income", "expense"}:
            label = "Kirim" if output.action == "income" else "Xarajat"
            if data.get("cancelled"):
                return (
                    f"↩️ #{data['entry_id']} yozuvi bekor qilingan.\n"
                    f"Balans: {format_money(int(str(data['balance'])))}"
                )
            return (
                f"✅ {label} saqlandi: #{data['entry_id']}\n{data['description']} — "
                f"{format_money(int(str(data['amount'])))}\n"
                f"Balans: {format_money(int(str(data['balance'])))}"
            )
        if output.action == "balance":
            return f"💰 Balans: {format_money(int(str(data['balance'])))}"
        if output.action == "report":
            kind = data.get("report_type", "summary")
            parts = {"income": "Kirim", "expense": "Xarajat", "salary": "Oylik"}
            report_lines = [f"📊 Hisobot: {str(data['month'])[:7]}"]
            for field, label in parts.items():
                if kind == "summary" or kind == field:
                    report_lines.append(f"{label}: {format_money(int(str(data[field])))}")
            closing_balance = format_money(int(str(data["closing_balance"])))
            report_lines.append(f"Oy oxiridagi balans: {closing_balance}")
            return "\n".join(report_lines)
    if output.action in {"list", "history"}:
        rows = cast(list[dict[str, JsonValue]], data.get("entries", []))
        lines = ["📋 Eslatmalar" if output.action == "list" else "📋 Yozuvlar tarixi"]
        for number, row in enumerate(rows, 1):
            detail = (
                f"{row['text']} · {row['time']} · {row['schedule']}"
                if output.action == "list"
                else f"{row['description']} · {format_money(int(str(row['amount'])))}"
                + (" · bekor qilingan" if row.get("cancelled") else "")
            )
            lines.append(f"{number}. #{row['id']}: {detail}")
        if not rows:
            lines.append("Hozircha yozuvlar yo‘q.")
        if data.get("more"):
            lines.append("Davomi uchun «Keyingi sahifa» deng.")
        return "\n\n".join(lines)
    return VOICE_HELP


async def send_text(message: Message, state: FSMContext, text: str) -> None:
    await state.clear()
    await message.answer(text, reply_markup=build_voice_menu(), parse_mode=None)


async def help_message(message: Message, state: FSMContext) -> None:
    await send_text(message, state, VOICE_HELP)


async def start_conversation(
    message: Message, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent
) -> None:
    context = await agent_context(message, handler_services)
    await send_text(message, state, VOICE_HELP)
    if await main_agent.has_pending(context.user_id, datetime.now(UTC)):
        output = await main_agent.resume(context=context, request_id=f"start:{message.message_id}")
        await send_text(message, state, response_text(output))


async def receive_conversation(
    message: Message, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent
) -> None:
    if message.from_user is None or message.chat.id != message.from_user.id:
        return
    if message.voice and (
        message.voice.duration > MAX_VOICE_SECONDS
        or (message.voice.file_size or 0) > MAX_VOICE_BYTES
    ):
        await send_text(message, state, "2 daqiqagacha va 5 MB dan kichik ovoz yuboring.")
        return
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
    context = await agent_context(message, handler_services)
    output = await main_agent.respond(
        context=context,
        request_id=f"{context.bot_id}:{message.chat.id}:m:{message.message_id}",
        text=text if audio is None else None,
        audio=audio,
        mime_type=(message.voice.mime_type or "audio/ogg") if message.voice else "audio/ogg",
    )
    await send_text(message, state, response_text(output))


async def retired_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Buyruqni ovoz bilan ayting.")
    if isinstance(callback.message, Message) and callback.message.chat.id == callback.from_user.id:
        await send_text(
            callback.message, state, "Endi buyruqlar ovoz orqali bajariladi. Kerakli ishni ayting."
        )


def build_voice_conversation_router(main_agent: MainAgent) -> Router:
    router = Router(name="voice-conversation")
    router.message.filter(F.chat.type == "private")
    router.message.register(start_conversation, CommandStart())
    router.message.register(help_message, Command("help"))
    router.message.register(help_message, F.text == HELP_LABEL)
    router.message.register(receive_conversation, F.voice | F.text)
    router.callback_query.register(retired_callback, F.message.chat.type == "private")
    return router
