"""User-controlled nasihat intervals in the prayer menu."""

from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from namoz_bot.domain.religious_intervals import ReligiousInterval
from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import (
    DAILY_SCHEDULE_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    SETTINGS_LABEL,
)


class ReligiousIntervalStates(StatesGroup):
    custom_hours = State()


INTERVAL_PANEL_ID = "nasihat_interval_panel_id"


def interval_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"Har {hours} soatda", callback_data=f"nasihat:set:{hours}")
        for hours in (1, 2, 4, 6, 12, 24)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:3],
            buttons[3:],
            [InlineKeyboardButton(text="✍️ Boshqa interval", callback_data="nasihat:custom")],
            [
                InlineKeyboardButton(
                    text="⏸ Avtomatik nasihatni o‘chirish", callback_data="nasihat:set:0"
                )
            ],
        ]
    )


def interval_text(item: ReligiousInterval) -> str:
    if not item.interval_hours:
        return (
            "⚙️ Nasihat intervali\n\nAvtomatik nasihat o‘chirilgan.\nYoqish uchun interval tanlang."
        )
    due = item.next_due.astimezone(ZoneInfo("Asia/Tashkent")) if item.next_due else None
    next_label = due.strftime("%d.%m.%Y %H:%M") if due else "—"
    return (
        f"⚙️ Nasihat intervali\n\nNasihat har {item.interval_hours:g} soatda keladi.\n"
        f"Keyingi yuborish: {next_label} (Toshkent vaqti).\n\n"
        "Yuborish vaqti soatning 00 daqiqasiga moslanadi.\n"
        "Interval joriy soatning boshidan hisoblanadi."
    )


async def show_interval(
    message: Message, handler_services: HandlerServices, state: FSMContext
) -> None:
    if handler_services.religious_intervals is None:
        await message.answer("Diniy eslatmalar hozircha sozlanmagan.")
        return
    assert message.from_user is not None
    await state.clear()
    item = await handler_services.religious_intervals.get(message.from_user.id)
    panel = await message.answer(
        interval_text(item), reply_markup=interval_keyboard(), parse_mode=None
    )
    await state.update_data({INTERVAL_PANEL_ID: panel.message_id})


async def choose_interval(
    callback: CallbackQuery, handler_services: HandlerServices, state: FSMContext
) -> None:
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        await callback.answer()
        return
    if (await state.get_data()).get(INTERVAL_PANEL_ID) != callback.message.message_id:
        await callback.answer("Bu menyu eskirgan. ⚙️ Nasihat intervali bo‘limini qayta oching.")
        return
    service = handler_services.religious_intervals
    if service is None:
        await callback.answer("Diniy eslatmalar hozircha sozlanmagan.")
        return
    if callback.data == "nasihat:custom":
        await state.set_state(ReligiousIntervalStates.custom_hours)
        await callback.message.answer(
            "Nasihat har necha soatda kelsin?\n"
            "1–168 oralig‘ida butun son yozing, masalan: 6.\n"
            "Chiqish uchun menyudagi boshqa tugmani bosing."
        )
        await callback.answer()
        return
    try:
        value = (callback.data or "").removeprefix("nasihat:set:")
        if not value.isascii() or not value.isdigit() or len(value) > 3:
            raise ValueError
        item = await service.set_interval(callback.from_user.id, int(value))
    except ValueError:
        await callback.answer("Interval 1–168 soat bo‘lishi kerak.", show_alert=True)
        return
    await state.clear()
    await state.update_data({INTERVAL_PANEL_ID: callback.message.message_id})
    try:
        await callback.message.edit_text(
            interval_text(item), reply_markup=interval_keyboard(), parse_mode=None
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
    await callback.answer("Saqlandi")


async def receive_interval(
    message: Message, handler_services: HandlerServices, state: FSMContext
) -> None:
    value = (message.text or "").strip()
    if (
        not value.isascii()
        or not value.isdigit()
        or not 1 <= len(value) <= 3
        or not 1 <= int(value) <= 168
    ):
        await message.answer("1–168 oralig‘ida butun soat miqdorini yozing, masalan: 6.")
        return
    assert message.from_user is not None and handler_services.religious_intervals is not None
    item = await handler_services.religious_intervals.set_interval(message.from_user.id, int(value))
    await state.clear()
    panel = await message.answer(
        interval_text(item), reply_markup=interval_keyboard(), parse_mode=None
    )
    await state.update_data({INTERVAL_PANEL_ID: panel.message_id})


def build_religious_settings_router() -> Router:
    router = Router(name="religious-settings")
    router.message.filter(F.chat.type == "private")
    router.message.register(show_interval, F.text == RELIGIOUS_INTERVAL_LABEL)
    router.callback_query.register(choose_interval, F.data.startswith("nasihat:"))
    router.message.register(
        receive_interval,
        ReligiousIntervalStates.custom_hours,
        ~F.text.startswith("/"),
        ~F.text.in_(
            {
                "⬅️ Asosiy menyu",
                "🕌 Namoz vaqti",
                "🔔 Eslatmalar",
                SETTINGS_LABEL,
                DAILY_SCHEDULE_LABEL,
            }
        ),
    )
    return router
