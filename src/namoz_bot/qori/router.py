"""Private Telegram reader and personal surah selection."""

import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import QORI_LABEL
from namoz_bot.presentation.reminder_panel import discard_panel
from namoz_bot.qori.corpus import Surah, chapters
from namoz_bot.qori.reading import reading_html
from namoz_bot.qori.selection import SurahSelection

PAGE_SIZE = 12
COMPACT_LABEL_LIMIT = 6
SAVED = "TANLANGAN SURALAR"
ADD = "Sura qo‘shish"
SOURCE = '<a href="https://tanzil.net/#{chapter}:{number}">Tanzil Project</a>'


def button(text: str, action: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data="qori:" + action)


def modes() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[button(SAVED, "saved:0")], [button(ADD, "catalog:0")]]
    )


def surah_list(selected: set[int], *, catalog: bool, page: int) -> tuple[str, InlineKeyboardMarkup]:
    items = [s for s in chapters() if catalog or s.number in selected]
    page = max(0, min(page, (len(items) - 1) // PAGE_SIZE))
    view = "catalog" if catalog else "saved"
    buttons = []
    for surah in items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]:
        label = surah.name
        action = "open"
        if catalog:
            if surah.number in selected:
                label = "✅ " + label
                action = "remove"
            else:
                action = "add"
        buttons.append(button(label, f"{action}:{surah.number}:{page}"))
    rows = []
    start = 0
    while start < len(buttons):
        row = buttons[start : start + 4]
        if any(len(b.text) > COMPACT_LABEL_LIMIT or b.text.startswith("✅") for b in row):
            row = row[:2]
        rows.append(row)
        start += len(row)
    nav = []
    if page:
        nav.append(button("⬅️ Oldingi", f"{view}:{page - 1}"))
    if (page + 1) * PAGE_SIZE < len(items):
        nav.append(button("Keyingi ➡️", f"{view}:{page + 1}"))
    if nav:
        rows.append(nav)
    if catalog:
        text = (
            f"{ADD} · {len(selected)} ta tanlangan\n"
            "Surani bosib qo‘shing. ✅ belgili surani bossangiz, u tanlovdan chiqadi."
        )
        rows.append([button(SAVED, "saved:0")])
    else:
        text = f"{SAVED}\n" + (
            "O‘qish uchun surani bosing." if items else "Hali sura tanlamagansiz."
        )
        rows.append([button(ADD, "catalog:0")])
    rows.append([button("⬅️ Qori", "menu")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def remember(
    state: FSMContext, message_id: int, keys: InlineKeyboardMarkup, *, reading: bool = False
) -> None:
    await state.update_data(
        qori_panel=message_id,
        qori_reading=reading,
        qori_actions=[b.callback_data for row in keys.inline_keyboard for b in row],
    )


async def open_qori(message: Message, state: FSMContext) -> None:
    await discard_panel(message, state)
    await state.clear()
    keys = modes()
    sent = await message.answer("📖 Qori\nBo‘limni tanlang.", reply_markup=keys)
    await remember(state, sent.message_id, keys)


async def show_text(
    message: Message, text: str, keys: InlineKeyboardMarkup, *, preserve: bool = False
) -> int:
    if message.photo or preserve:
        # Telegram can turn text into media, but a photo cannot be edited back to text.
        sent = await message.answer(text, reply_markup=keys)
        await message.edit_reply_markup(reply_markup=None)
        return sent.message_id
    await message.edit_text(text, reply_markup=keys)
    return message.message_id


async def send_reading(
    message: Message, state: FSMContext, surah: Surah, keys: InlineKeyboardMarkup
) -> None:
    source = SOURCE.format(chapter=surah.number, number=1)
    request = message.answer_document(
        BufferedInputFile(reading_html(surah), filename=f"{surah.name}.html"),
        caption=f"{surah.name} surasi · To‘liq rangli matn\n{source}",
        parse_mode="HTML",
        reply_markup=keys,
    )
    try:
        sent = await request
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        sent = await request
    await remember(state, sent.message_id, keys, reading=True)
    await message.edit_reply_markup(reply_markup=None)


async def navigate(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    surah_selection: SurahSelection,
) -> None:
    message, action = callback.message, callback.data
    data = await state.get_data()
    if (
        not isinstance(message, Message)
        or message.chat.id != callback.from_user.id
        or not action
        or data.get("qori_panel") != message.message_id
        or action not in data.get("qori_actions", [])
    ):
        await callback.answer("Qori menyusini qayta oching.")
        return
    await callback.answer()
    _, command, *args = action.split(":")
    if command == "menu":
        keys = modes()
        panel = await show_text(message, "📖 Qori\nBo‘limni tanlang.", keys)
    else:
        user = await handler_services.subscriptions.get(callback.from_user.id)
        assert user.id is not None
        page = int(args[-1])
        if command in {"add", "remove"}:
            await surah_selection.set_selected(user.id, int(args[0]), selected=command == "add")
        selected = await surah_selection.list_for(user.id)
        if command == "open" and int(args[0]) in selected:
            keys = InlineKeyboardMarkup(inline_keyboard=[[button("⬅️ " + SAVED, f"saved:{page}")]])
            await send_reading(message, state, chapters()[int(args[0]) - 1], keys)
            return
        text, keys = surah_list(
            selected, catalog=command in {"catalog", "add", "remove"}, page=page
        )
        panel = await show_text(message, text, keys, preserve=data.get("qori_reading", False))
    await remember(state, panel, keys)


def build_qori_router() -> Router:
    router = Router(name="qori")
    router.message.filter(F.chat.type == "private")
    router.message.register(open_qori, F.text == QORI_LABEL)
    router.message.register(open_qori, Command("qori"))
    router.callback_query.register(navigate, F.data.startswith("qori:"))
    return router
