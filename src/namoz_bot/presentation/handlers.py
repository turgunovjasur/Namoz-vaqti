"""Thin aiogram handlers delegating all business rules to services."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from namoz_bot.application.schedules import ScheduleService, format_schedule
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.errors import ScheduleValidationError, UnsupportedRegionError
from namoz_bot.domain.models import (
    PRAYER_KEYS,
    OffsetAction,
    PrayerKey,
    PrayerOffsets,
    UserSubscription,
)
from namoz_bot.domain.regions import get_region, get_region_group
from namoz_bot.presentation.keyboards import (
    DISABLE_LABEL,
    ENABLE_LABEL,
    HELP_LABEL,
    OFFSETS_LABEL,
    PRAYER_LABELS,
    REGION_LABEL,
    TODAY_LABEL,
    build_main_menu,
    build_offset_adjustment_keyboard,
    build_offsets_keyboard,
    build_region_group_keyboard,
    build_region_keyboard,
    format_offset_value,
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


async def _send_today(
    message: Any,
    services: HandlerServices,
    subscription: UserSubscription,
) -> None:
    schedule = await services.schedules.get_today(subscription.region_code, services.today())
    await message.answer(
        format_schedule(schedule, relative_label="Bugun", offsets=subscription.offsets),
        reply_markup=build_main_menu(is_active=subscription.is_active),
    )


async def handle_start(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, chat_id = _message_identity(message)
    result = await handler_services.subscriptions.start(telegram_user_id, chat_id)
    await _send_today(message, handler_services, result.subscription)


async def handle_today(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, _ = _message_identity(message)
    subscription = await handler_services.subscriptions.get(telegram_user_id)
    await _send_today(message, handler_services, subscription)


async def handle_settings(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, _ = _message_identity(message)
    subscription = await handler_services.subscriptions.get(telegram_user_id)
    region = get_region(subscription.region_code)
    await message.answer(
        f"Joriy hudud: {region.display_name}\nYangi hududni tanlang:",
        reply_markup=build_region_group_keyboard(),
    )


def _format_offsets_overview(offsets: PrayerOffsets) -> str:
    lines = ["⏱ Shaxsiy vaqt farqlari", ""]
    lines.extend(
        f"{label}: {format_offset_value(offsets.value_for(prayer))}"
        for prayer, label in PRAYER_LABELS.items()
    )
    return "\n".join(lines)


def _format_offset_detail(prayer: PrayerKey, value: int) -> str:
    return (
        f"⏱ {PRAYER_LABELS[prayer]} vaqtini sozlash\n\n"
        f"Joriy farq: {format_offset_value(value)}\n\n"
        "Har bosishda vaqt 1 daqiqaga o‘zgaradi. 0 — standart vaqtga qaytaradi."
    )


def _parse_prayer_callback(data: str | None) -> PrayerKey | None:
    if data is None:
        return None
    parts = data.split(":")
    if len(parts) != 2 or parts[0] != "offset" or parts[1] not in PRAYER_KEYS:
        return None
    return parts[1]


def _parse_offset_change(data: str | None) -> tuple[PrayerKey, OffsetAction] | None:
    if data is None:
        return None
    parts = data.split(":")
    actions: dict[str, OffsetAction] = {"-1": -1, "0": 0, "1": 1}
    if (
        len(parts) != 3
        or parts[0] != "offset-change"
        or parts[1] not in PRAYER_KEYS
        or parts[2] not in actions
    ):
        return None
    return parts[1], actions[parts[2]]


async def handle_offsets(message: Message, handler_services: HandlerServices) -> None:
    telegram_user_id, _ = _message_identity(message)
    subscription = await handler_services.subscriptions.get(telegram_user_id)
    await message.answer(
        _format_offsets_overview(subscription.offsets),
        reply_markup=build_offsets_keyboard(subscription.offsets),
    )


async def handle_offsets_overview(
    callback: CallbackQuery,
    handler_services: HandlerServices,
) -> None:
    if callback.message is None:
        await callback.answer("So‘rov noto‘g‘ri", show_alert=True)
        return
    subscription = await handler_services.subscriptions.get(callback.from_user.id)
    message = cast(Any, callback.message)
    await message.edit_text(
        _format_offsets_overview(subscription.offsets),
        reply_markup=build_offsets_keyboard(subscription.offsets),
    )
    await callback.answer()


async def handle_offset_selection(
    callback: CallbackQuery,
    handler_services: HandlerServices,
) -> None:
    prayer = _parse_prayer_callback(callback.data)
    if callback.message is None or prayer is None:
        await callback.answer("So‘rov noto‘g‘ri", show_alert=True)
        return
    subscription = await handler_services.subscriptions.get(callback.from_user.id)
    value = subscription.offsets.value_for(prayer)
    message = cast(Any, callback.message)
    await message.edit_text(
        _format_offset_detail(prayer, value),
        reply_markup=build_offset_adjustment_keyboard(prayer, value),
    )
    await callback.answer()


async def handle_offset_change(
    callback: CallbackQuery,
    handler_services: HandlerServices,
) -> None:
    parsed = _parse_offset_change(callback.data)
    if callback.message is None or parsed is None:
        await callback.answer("So‘rov noto‘g‘ri", show_alert=True)
        return
    prayer, action = parsed
    try:
        subscription = await handler_services.subscriptions.change_offset(
            callback.from_user.id,
            prayer,
            action,
        )
    except ScheduleValidationError:
        await callback.answer(
            "Chegara: \N{MINUS SIGN}30…+30 daqiqa",
            show_alert=True,
        )
        return
    value = subscription.offsets.value_for(prayer)
    message = cast(Any, callback.message)
    await message.edit_text(
        _format_offset_detail(prayer, value),
        reply_markup=build_offset_adjustment_keyboard(prayer, value),
    )
    await callback.answer()


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

    subscription = await handler_services.subscriptions.change_region(
        callback.from_user.id,
        region.code,
    )
    schedule = await handler_services.schedules.get_today(region.code, handler_services.today())
    await callback.message.answer(
        format_schedule(schedule, relative_label="Bugun", offsets=subscription.offsets),
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
        "yuboradi. /today — bugungi jadval, /settings — hudud va xabar sozlamalari, "
        "/offsets — saqlanadigan shaxsiy vaqt farqlari."
    )


router.message.register(handle_start, CommandStart())
router.message.register(handle_today, Command("today"))
router.message.register(handle_settings, Command("settings"))
router.message.register(handle_offsets, Command("offsets"))
router.message.register(handle_help, Command("help"))
router.message.register(handle_today, F.text == TODAY_LABEL)
router.message.register(handle_settings, F.text == REGION_LABEL)
router.message.register(handle_offsets, F.text == OFFSETS_LABEL)
router.message.register(handle_toggle_notifications, F.text.in_({DISABLE_LABEL, ENABLE_LABEL}))
router.message.register(handle_help, F.text == HELP_LABEL)
router.callback_query.register(handle_region_groups, F.data == "region-groups")
router.callback_query.register(handle_offsets_overview, F.data == "offsets")
router.callback_query.register(handle_offset_change, F.data.startswith("offset-change:"))
router.callback_query.register(handle_offset_selection, F.data.startswith("offset:"))
router.callback_query.register(
    handle_region_group_selection,
    F.data.startswith("region-group:"),
)
router.callback_query.register(handle_region_selection, F.data.startswith("region:"))
