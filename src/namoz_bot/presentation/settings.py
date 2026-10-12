"""Settings navigation and personal daily schedule delivery time."""

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from namoz_bot.domain.daily_schedule import DailySchedulePreference
from namoz_bot.domain.reminders import TASHKENT, parse_time
from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import (
    DAILY_SCHEDULE_LABEL,
    HOME_LABEL,
    PRAYER_MENU_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    REMINDERS_LABEL,
    SETTINGS_LABEL,
    build_settings_menu,
)

DAILY_PANEL_ID = "daily_settings_panel_id"


class DailySettingsStates(StatesGroup):
    custom_time = State()


def daily_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=value, callback_data=f"daily:set:{value}")
        for value in ("06:00", "08:00", "12:00", "18:00", "21:00", "22:00")
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:3],
            buttons[3:],
            [InlineKeyboardButton(text="✍️ Boshqa vaqt", callback_data="daily:custom")],
        ]
    )


def daily_text(item: DailySchedulePreference) -> str:
    return (
        "📅 Kunlik jadval\n\n"
        f"Ertangi kunning namoz jadvali har kuni {item.at:%H:%M} da yuboriladi.\n"
        f"Keyingi yuborish: {item.next_due.astimezone(TASHKENT):%d.%m.%Y %H:%M}.\n"
        "Vaqtlar Toshkent vaqti bo‘yicha.\n\nYuborish vaqtini tanlang."
    )


async def show_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("⚙️ Sozlamalar. Bo‘limni tanlang:", reply_markup=build_settings_menu())


async def show_daily(
    message: Message, state: FSMContext, handler_services: HandlerServices
) -> None:
    assert message.from_user is not None and handler_services.daily_settings is not None
    await state.clear()
    item = await handler_services.daily_settings.get(message.from_user.id)
    panel = await message.answer(daily_text(item), reply_markup=daily_keyboard())
    await state.update_data({DAILY_PANEL_ID: panel.message_id})


async def choose_daily(
    callback: CallbackQuery, state: FSMContext, handler_services: HandlerServices
) -> None:
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        await callback.answer()
        return
    if (await state.get_data()).get(DAILY_PANEL_ID) != callback.message.message_id:
        await callback.answer("Bu menyu eskirgan. 📅 Kunlik jadval bo‘limini qayta oching.")
        return
    if callback.data == "daily:custom":
        await state.set_state(DailySettingsStates.custom_time)
        await callback.message.answer(
            "Har kuni jadval qaysi vaqtda kelsin?\n"
            "Vaqtni HH:MM shaklida yozing, masalan: 07:30.\n"
            "Chiqish uchun menyudagi boshqa tugmani bosing."
        )
        await callback.answer()
        return
    try:
        at = parse_time((callback.data or "").removeprefix("daily:set:"))
    except ValueError:
        await callback.answer("Vaqtni HH:MM shaklida tanlang.", show_alert=True)
        return
    assert handler_services.daily_settings is not None
    item = await handler_services.daily_settings.set_time(callback.from_user.id, at)
    await state.clear()
    await state.update_data({DAILY_PANEL_ID: callback.message.message_id})
    try:
        await callback.message.edit_text(daily_text(item), reply_markup=daily_keyboard())
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
    await callback.answer("Saqlandi")


async def receive_daily(
    message: Message, state: FSMContext, handler_services: HandlerServices
) -> None:
    try:
        at = parse_time(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    assert message.from_user is not None and handler_services.daily_settings is not None
    item = await handler_services.daily_settings.set_time(message.from_user.id, at)
    await state.clear()
    panel = await message.answer(daily_text(item), reply_markup=daily_keyboard())
    await state.update_data({DAILY_PANEL_ID: panel.message_id})


def build_settings_router() -> Router:
    router = Router(name="settings")
    router.message.filter(F.chat.type == "private")
    router.message.register(show_settings, F.text == SETTINGS_LABEL)
    router.message.register(show_daily, F.text == DAILY_SCHEDULE_LABEL)
    router.callback_query.register(choose_daily, F.data.startswith("daily:"))
    router.message.register(
        receive_daily,
        DailySettingsStates.custom_time,
        ~F.text.startswith("/"),
        ~F.text.in_(
            {
                HOME_LABEL,
                PRAYER_MENU_LABEL,
                REMINDERS_LABEL,
                SETTINGS_LABEL,
                RELIGIOUS_INTERVAL_LABEL,
            }
        ),
    )
    return router
