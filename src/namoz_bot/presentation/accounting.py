"""Private finance mode with exact reports and owner-scoped reversible records."""

import asyncio
from datetime import date
from io import BytesIO

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.voice_reminders import MAX_VOICE_BYTES, MAX_VOICE_SECONDS
from namoz_bot.domain.accounting import CATEGORY_LABELS, LedgerEntry, LedgerSummary, format_money
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import (
    ACCOUNTING_LABEL,
    ADD_LABEL,
    DAILY_SCHEDULE_LABEL,
    HELP_LABEL,
    HOME_LABEL,
    LIST_LABEL,
    OFFSETS_LABEL,
    PRAYER_MENU_LABEL,
    REGION_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    RELIGIOUS_REMINDER_LABEL,
    REMINDERS_LABEL,
    SETTINGS_LABEL,
    TODAY_LABEL,
    TODAY_REMINDERS_LABEL,
)
from namoz_bot.presentation.reminder_keyboards import MONTHS
from namoz_bot.presentation.reminder_panel import (
    KEEP_MAIN_MENU,
    PANEL_ID,
    delete_input,
    discard_panel,
    render_panel,
    show_main_menu,
)


class AccountingStates(StatesGroup):
    active = State()


def _month_label(month: date) -> str:
    return f"{MONTHS[month.month - 1]} {month.year}"


def _button(owner: int, text: str, action: str, value: str = "-") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=f"acct:{owner}:{action}:{value}")


def _keyboard(owner: int, entry: LedgerEntry | None = None) -> InlineKeyboardMarkup:
    rows = []
    if entry is not None and not entry.cancelled:
        rows.append([_button(owner, "↩️ Yozuvni bekor qilish", "undo", str(entry.id))])
    rows.extend(
        [
            [
                _button(owner, "💳 Balans", "balance"),
                _button(owner, "📊 Shu oy hisoboti", "summary"),
            ],
            [_button(owner, "📒 Tarix", "history", "0")],
            [_button(owner, "⬅️ Asosiy menyu", "home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _summary_text(summary: LedgerSummary, report_type: str = "summary") -> str:
    title = f"📊 {_month_label(summary.month)}"
    if report_type != "summary":
        label, amount = {
            "salary": ("Oylik tushumi", summary.salary),
            "income": ("Jami kirim", summary.income),
            "expense": ("Jami chiqim", summary.expense),
        }[report_type]
        return f"{title}\n\n{label}: {format_money(amount)}"
    return (
        f"{title}\n\nOldingi oylar qoldig‘i: {format_money(summary.opening_balance)}\n"
        f"Jami kirim: {format_money(summary.income)}\n"
        f"Oylik tushumi: {format_money(summary.salary)}\n"
        f"Jami chiqim: {format_money(summary.expense)}\n"
        f"Oy farqi: {format_money(summary.income - summary.expense)}\n"
        f"Oy yakunidagi qoldiq: {format_money(summary.closing_balance)}"
    )


async def _owner(services: HandlerServices, telegram_id: int, chat_id: int) -> int:
    owner = (await services.subscriptions.start(telegram_id, chat_id)).subscription.id
    assert owner is not None
    return owner


async def open_accounting(
    message: Message,
    state: FSMContext,
    handler_services: HandlerServices,
    ledger_service: LedgerService,
) -> None:
    assert message.from_user is not None
    owner = await _owner(handler_services, message.from_user.id, message.chat.id)
    await discard_panel(message, state)
    await state.clear()
    await state.update_data({KEEP_MAIN_MENU: True})
    await state.set_state(AccountingStates.active)
    await render_panel(
        message,
        state,
        "💰 Kirim-chiqim\n\n"
        f"Joriy balans: {format_money(await ledger_service.balance(owner))}\n\n"
        "Ovoz yoki matn bilan bitta kirim/chiqimni ayting:\n"
        "«Oktyabrda 10 million oylik tushdi»\n«120 mingga kiyim oldim»\n\n"
        "Hisobot: «Oktyabrda qancha sarfladim?» yoki «Balansim qancha?»\n"
        "Valyuta: so‘m. Aniq yozuv darhol saqlanadi, bekor qilish mumkin.",
        _keyboard(message.from_user.id),
    )


async def _show_history(
    message: Message,
    state: FSMContext,
    service: LedgerService,
    owner: int,
    telegram_id: int,
    page: int,
) -> None:
    entries, more = await service.history(owner, page)
    text = "📒 Kirim-chiqim tarixi\n\n"
    if not entries:
        text += "Hozircha yozuvlar yo‘q."
    rows = []
    for entry in entries:
        stamp = (
            f"{entry.occurred_on:%d.%m.%Y}"
            if entry.occurred_on
            else _month_label(entry.period) + " (kun aytilmagan)"
        )
        kind = "Kirim" if entry.kind == "income" else "Chiqim"
        text += (
            f"#{entry.id} · {kind} · {format_money(entry.amount)}\n"
            f"{entry.description} · {CATEGORY_LABELS[entry.category]}\n{stamp}"
            + (" · Bekor qilingan" if entry.cancelled else "")
            + "\n\n"
        )
        if not entry.cancelled:
            rows.append(
                [_button(telegram_id, f"↩️ #{entry.id} ni bekor qilish", "undo", str(entry.id))]
            )
    navigation = []
    if page:
        navigation.append(_button(telegram_id, "⬅️ Oldingi", "history", str(page - 1)))
    if more:
        navigation.append(_button(telegram_id, "Keyingi ➡️", "history", str(page + 1)))
    if navigation:
        rows.append(navigation)
    rows.extend(_keyboard(telegram_id).inline_keyboard)
    await render_panel(message, state, text, InlineKeyboardMarkup(inline_keyboard=rows))


async def receive_accounting(
    message: Message,
    state: FSMContext,
    handler_services: HandlerServices,
    ledger_service: LedgerService,
) -> None:
    assert message.from_user is not None
    telegram_id = message.from_user.id
    owner = await _owner(handler_services, telegram_id, message.chat.id)
    if not ledger_service.input_enabled:
        await render_panel(
            message, state, "Kirim-chiqim AI xizmati sozlanmagan.", _keyboard(telegram_id)
        )
        return
    if message.voice and (
        message.voice.duration > MAX_VOICE_SECONDS
        or (message.voice.file_size or 0) > MAX_VOICE_BYTES
    ):
        await render_panel(
            message,
            state,
            "2 daqiqagacha va 5 MB dan kichik qisqa ovoz yuboring.",
            _keyboard(telegram_id),
        )
        return
    progress = await message.answer("🎙 Kirim-chiqim xabaringiz tahlil qilinmoqda…")
    try:
        audio = None
        if message.voice:
            assert message.bot is not None
            buffer = BytesIO()
            await asyncio.wait_for(
                message.bot.download(message.voice.file_id, destination=buffer), 20
            )
            audio = buffer.getvalue()
        request = await ledger_service.extract(
            text=message.text if audio is None else None,
            audio=audio,
            mime_type=(message.voice.mime_type or "audio/ogg") if message.voice else "audio/ogg",
            now=message.date,
        )
    except ValueError as exc:
        await render_panel(message, state, str(exc), _keyboard(telegram_id))
        return
    except (ExternalServiceError, TelegramAPIError, TimeoutError, OSError):
        await render_panel(
            message,
            state,
            "Kirim-chiqim xabarini tushunib bo‘lmadi. Birozdan keyin qayta yuboring.",
            _keyboard(telegram_id),
        )
        return
    finally:
        await delete_input(progress)
    if request.intent in {"unclear", "unsupported"} or request.clarification:
        await render_panel(
            message,
            state,
            request.clarification
            or (
                "Bitta amalga oshgan kirim yoki chiqimni so‘mda aniq ayting. "
                "Masalan: «120 mingga kiyim oldim». Hisobotlar oy bo‘yicha olinadi."
            ),
            _keyboard(telegram_id),
        )
        return
    entry = None
    try:
        if request.intent in {"income", "expense"}:
            entry = await ledger_service.record(
                owner, request, f"telegram:{message.chat.id}:{message.message_id}", message.date
            )
            if entry.cancelled:
                text = "Bu xabardagi yozuv avval bekor qilingan. Qayta hisobga qo‘shilmadi."
            else:
                title = "Kirim qayd etildi" if entry.kind == "income" else "Chiqim qayd etildi"
                stamp = (
                    f"{entry.occurred_on:%d.%m.%Y}"
                    if entry.occurred_on
                    else _month_label(entry.period) + " (kun aytilmagan)"
                )
                text = (
                    f"✅ {title}\n\n{format_money(entry.amount)}\n"
                    f"{entry.description} · {CATEGORY_LABELS[entry.category]}\n📅 {stamp}"
                )
            text += f"\n\nJoriy balans: {format_money(await ledger_service.balance(owner))}"
        elif request.intent == "report":
            text = _summary_text(
                await ledger_service.summary(owner, request.period(message.date)),
                request.report_type or "summary",
            )
        elif request.intent == "history":
            await _show_history(message, state, ledger_service, owner, telegram_id, 0)
            return
        else:
            text = f"💳 Joriy balans: {format_money(await ledger_service.balance(owner))}"
    except ValueError as exc:
        await render_panel(message, state, str(exc), _keyboard(telegram_id))
        return
    await render_panel(message, state, text, _keyboard(telegram_id, entry))


async def accounting_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    ledger_service: LedgerService,
) -> None:
    message = callback.message
    parts = (callback.data or "").split(":")
    if (
        not isinstance(message, Message)
        or message.chat.type != "private"
        or len(parts) != 4
        or parts[1] != str(callback.from_user.id)
        or message.chat.id != callback.from_user.id
    ):
        await callback.answer("Bu yozuv sizga tegishli emas.", show_alert=True)
        return
    action, value = parts[2], parts[3]
    active = await state.get_state() == AccountingStates.active.state
    data = await state.get_data()
    if action != "undo" and (not active or data.get(PANEL_ID) != message.message_id):
        await callback.answer("Kirim-chiqim bo‘limini qayta oching.", show_alert=True)
        return
    owner = await _owner(handler_services, callback.from_user.id, message.chat.id)
    try:
        if action == "undo":
            if not value.isdigit():
                raise ValueError("Yozuv raqami noto‘g‘ri.")
            cancelled = await ledger_service.cancel(owner, int(value))
            text = (
                "↩️ Yozuv bekor qilindi."
                if cancelled
                else "Bu yozuv topilmadi yoki avval bekor qilingan."
            )
            text += f"\n\nJoriy balans: {format_money(await ledger_service.balance(owner))}"
            if active:
                await render_panel(message, state, text, _keyboard(callback.from_user.id))
            else:
                await message.answer(text, parse_mode=None)
        elif action == "home":
            await show_main_menu(message, state)
        elif action == "history":
            await _show_history(
                message, state, ledger_service, owner, callback.from_user.id, int(value)
            )
        else:
            if action == "summary":
                month = ledger_service_month()
                text = _summary_text(await ledger_service.summary(owner, month))
            elif action == "balance":
                text = f"💳 Joriy balans: {format_money(await ledger_service.balance(owner))}"
            else:
                raise ValueError("Amal noto‘g‘ri.")
            await render_panel(message, state, text, _keyboard(callback.from_user.id))
    except (ValueError, OverflowError):
        await callback.answer("Amal yoki yozuv raqami noto‘g‘ri.", show_alert=True)
        return
    await callback.answer()


def ledger_service_month() -> date:
    from datetime import datetime

    return datetime.now(TASHKENT).date().replace(day=1)


def build_accounting_router() -> Router:
    router = Router(name="accounting")
    router.message.filter(F.chat.type == "private")
    router.message.register(open_accounting, F.text == ACCOUNTING_LABEL)
    router.message.register(receive_accounting, AccountingStates.active, F.voice)
    navigation = {
        ACCOUNTING_LABEL,
        REMINDERS_LABEL,
        PRAYER_MENU_LABEL,
        HOME_LABEL,
        SETTINGS_LABEL,
        TODAY_LABEL,
        REGION_LABEL,
        OFFSETS_LABEL,
        HELP_LABEL,
        RELIGIOUS_REMINDER_LABEL,
        RELIGIOUS_INTERVAL_LABEL,
        DAILY_SCHEDULE_LABEL,
        ADD_LABEL,
        LIST_LABEL,
        TODAY_REMINDERS_LABEL,
    }
    router.message.register(
        receive_accounting,
        AccountingStates.active,
        F.text,
        ~F.text.startswith("/"),
        ~F.text.in_(navigation),
    )
    router.callback_query.register(accounting_callback, F.data.startswith("acct:"))
    return router
