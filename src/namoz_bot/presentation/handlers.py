"""Thin aiogram handlers delegating all business rules to services."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from namoz_bot.application.schedules import ScheduleService, format_schedule
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.errors import UnsupportedRegionError
from namoz_bot.domain.regions import get_region, get_region_group
from namoz_bot.presentation.keyboards import (
    DISABLE_LABEL,
    ENABLE_LABEL,
    HELP_LABEL,
    REGION_LABEL,
    TODAY_LABEL,
    build_main_menu,
    build_region_group_keyboard,
    build_region_keyboard,
)

router = Router(name="public-bot")


@dataclass(frozen=True, slots=True)
class HandlerServices:
    """Request-scoped application services injected by middleware."""

    subscriptions: SubscriptionService
    schedules: ScheduleService
    today: Callable[[], date]


def _message_identity(message: Any) -> tuple[int, int]:
    if message.from_user is None:
        raise ValueError("Telegram foydalanuvchisi mavjud emas")
    return int(message.from_user.id), int(message.chat.id)


async def _send_today(message: Any, services: HandlerServices, region_code: str) -> None:
    schedule = await services.schedules.get_today(region_code, services.today())
    subscription = await services.subscriptions.get(_message_identity(message)[0])
    await message.answer(
        format_schedule(schedule, relative_label="Bugun"),
        reply_markup=build_main_menu(is_active=subscription.is_active),
    )


async def handle_start(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, chat_id = _message_identity(message)
    result = await handler_services.subscriptions.start(telegram_user_id, chat_id)
    await _send_today(message, handler_services, result.subscription.region_code)


async def handle_today(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, _ = _message_identity(message)
    subscription = await handler_services.subscriptions.get(telegram_user_id)
    await _send_today(message, handler_services, subscription.region_code)


async def handle_settings(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, _ = _message_identity(message)
    subscription = await handler_services.subscriptions.get(telegram_user_id)
    region = get_region(subscription.region_code)
    await message.answer(
        f"Joriy hudud: {region.display_name}\nYangi hududni tanlang:",
        reply_markup=build_region_group_keyboard(),
    )


async def handle_region_groups(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer("So‘rov noto‘g‘ri", show_alert=True)
        return
    await callback.message.answer(
        "Viloyat yoki hudud guruhini tanlang:",
        reply_markup=build_region_group_keyboard(),
    )
    await callback.answer()


async def handle_region_group_selection(callback: CallbackQuery) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer("So‘rov noto‘g‘ri", show_alert=True)
        return
    group_code = callback.data.removeprefix("region-group:")
    try:
        group = get_region_group(group_code)
        keyboard = build_region_keyboard(group_code=group.code)
    except UnsupportedRegionError:
        await callback.answer("Hudud guruhi topilmadi", show_alert=True)
        return
    await callback.message.answer(
        f"{group.display_name}: shahar yoki tumanni tanlang:",
        reply_markup=keyboard,
    )
    await callback.answer()


async def handle_region_selection(
    callback: CallbackQuery,
    handler_services: HandlerServices,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer("So‘rov noto‘g‘ri", show_alert=True)
        return
    region_code = callback.data.removeprefix("region:")
    if ":" in region_code:
        await callback.answer(
            "Menyu yangilangan. /settings ni qayta oching",
            show_alert=True,
        )
        return
    try:
        region = get_region(region_code)
    except UnsupportedRegionError:
        await callback.answer("Hudud topilmadi", show_alert=True)
        return

    await handler_services.subscriptions.change_region(callback.from_user.id, region.code)
    schedule = await handler_services.schedules.get_today(region.code, handler_services.today())
    subscription = await handler_services.subscriptions.get(callback.from_user.id)
    await callback.message.answer(
        format_schedule(schedule, relative_label="Bugun"),
        reply_markup=build_main_menu(is_active=subscription.is_active),
    )
    await callback.answer("Hudud saqlandi")


async def handle_toggle_notifications(
    message: Message,
    handler_services: HandlerServices,
) -> None:
    telegram_user_id, _ = _message_identity(message)
    current = await handler_services.subscriptions.get(telegram_user_id)
    updated = await handler_services.subscriptions.set_active(
        telegram_user_id, not current.is_active
    )
    status = "yoqildi" if updated.is_active else "o‘chirildi"
    await message.answer(
        f"Kunlik xabarlar {status}.",
        reply_markup=build_main_menu(is_active=updated.is_active),
    )


async def handle_help(message: Message) -> None:
    await message.answer(
        "Bot har kuni soat 21:00 da tanlangan hudud uchun ertangi namoz vaqtlarini "
        "yuboradi. /today — bugungi jadval, /settings — hudud va xabar sozlamalari."
    )


router.message.register(handle_start, CommandStart())
router.message.register(handle_today, Command("today"))
router.message.register(handle_settings, Command("settings"))
router.message.register(handle_help, Command("help"))
router.message.register(handle_today, F.text == TODAY_LABEL)
router.message.register(handle_settings, F.text == REGION_LABEL)
router.message.register(handle_toggle_notifications, F.text.in_({DISABLE_LABEL, ENABLE_LABEL}))
router.message.register(handle_help, F.text == HELP_LABEL)
router.callback_query.register(handle_region_groups, F.data == "region-groups")
router.callback_query.register(
    handle_region_group_selection,
    F.data.startswith("region-group:"),
)
router.callback_query.register(handle_region_selection, F.data.startswith("region:"))
