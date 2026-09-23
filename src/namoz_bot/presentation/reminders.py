"""Private reminder dialog and two-section navigation."""

from datetime import date
from typing import Any
from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from namoz_bot.application.reminders import ReminderService
from namoz_bot.domain.reminders import TASHKENT, ReminderSpec, parse_time
from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import (
    ADD_LABEL,
    HOME_LABEL,
    LIST_LABEL,
    PRAYER_MENU_LABEL,
    REMINDERS_LABEL,
    build_main_menu,
    build_prayer_menu,
    build_reminders_menu,
)
from namoz_bot.presentation.reminder_keyboards import dialog_keyboard, page_keyboard


class ReminderStates(StatesGroup):
    text = State()
    time = State()
    schedule = State()
    date = State()
    weekday = State()
    confirm = State()


def _spec(data: dict[str, Any]) -> ReminderSpec:
    return ReminderSpec(
        data["text"],
        parse_time(data["time"]),
        data["kind"],
        date.fromisoformat(data["date"]) if data.get("date") else None,
        data.get("weekday"),
    )


async def _private(message: Message) -> bool:
    if message.chat.type != "private":
        await message.answer("Eslatmalarni bot bilan shaxsiy chatda oching.")
        return False
    return True


async def show_section(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.text == PRAYER_MENU_LABEL:
        await message.answer("🕌 Namoz vaqti. Amalni tanlang:", reply_markup=build_prayer_menu())
    elif message.text == REMINDERS_LABEL:
        if await _private(message):
            await message.answer(
                "🔔 Eslatmalar. Amalni tanlang:", reply_markup=build_reminders_menu()
            )
    else:
        await message.answer("Asosiy menyu. Bo‘limni tanlang:", reply_markup=build_main_menu())


async def _prompt(
    message: Message,
    state: FSMContext,
    step: str,
    service: ReminderService,
    month: date | None = None,
) -> None:
    data = await state.get_data()
    token = uuid4().hex[:16]
    await state.update_data(token=token, step=step)
    await state.set_state(getattr(ReminderStates, step))
    today = service.now().astimezone(TASHKENT).date()
    prompts = {
        "text": "Eslatma matnini yozing (1–1000 belgi):",
        "time": "Soat nechada eslatay? HH:MM shaklida kiriting.\nToshkent vaqti bo‘yicha.",
        "schedule": "Qachon eslatay?",
        "date": "Sanani tanlang:",
        "weekday": "Haftaning qaysi kuni eslatay?",
    }
    text = prompts.get(step, "")
    if step == "confirm":
        spec = _spec(data)
        text = f"📝 {spec.text}\n🕒 {spec.at:%H:%M} · Toshkent\n📅 {spec.schedule_label()}"
    await message.answer(
        text,
        reply_markup=dialog_keyboard(token, step, month=month or today.replace(day=1), today=today),
        parse_mode=None,
    )


async def start_reminder(
    message: Message,
    state: FSMContext,
    reminder_service: ReminderService,
    handler_services: HandlerServices,
) -> None:
    await state.clear()
    if not await _private(message) or message.from_user is None:
        return
    user = await handler_services.subscriptions.start(message.from_user.id, message.chat.id)
    await state.update_data(creation_token=uuid4().hex, user_id=user.subscription.id)
    await _prompt(message, state, "text", reminder_service)


async def receive_text(
    message: Message, state: FSMContext, reminder_service: ReminderService
) -> None:
    if not await _private(message):
        return
    value = (message.text or "").strip()
    if not 1 <= len(value) <= 1000:
        await message.answer("Eslatma matni 1–1000 belgidan iborat bo‘lsin.")
        return
    await state.update_data(text=value)
    await _prompt(message, state, "time", reminder_service)


async def receive_time(
    message: Message, state: FSMContext, reminder_service: ReminderService
) -> None:
    try:
        at = parse_time(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(time=at.strftime("%H:%M"))
    await _prompt(message, state, "schedule", reminder_service)


async def dialog_callback(
    callback: CallbackQuery, state: FSMContext, reminder_service: ReminderService
) -> None:
    message = callback.message
    if not isinstance(message, Message) or message.chat.type != "private":
        await callback.answer("Eslatmalarni shaxsiy chatda oching.", show_alert=True)
        return
    data = await state.get_data()
    parts = (callback.data or "").split(":")
    if (
        len(parts) != 4
        or parts[1] != data.get("token")
        or message.chat.id != callback.from_user.id
        or not await state.get_state()
    ):
        await callback.answer(
            "Bu tugma eskirgan. Eslatmalar menyusini qayta oching.", show_alert=True
        )
        return
    _, _, action, value = parts
    step = data["step"]
    try:
        if action == "noop":
            pass
        elif action == "cancel" or (action == "back" and step == "text"):
            await state.clear()
            await message.answer("Bekor qilindi.", reply_markup=build_reminders_menu())
        elif action == "back":
            previous = {
                "time": "text",
                "schedule": "time",
                "date": "schedule",
                "weekday": "schedule",
                "confirm": {
                    "once": "date",
                    "weekly": "weekday",
                    "daily": "schedule",
                }.get(data.get("kind", ""), "schedule"),
            }[step]
            await _prompt(message, state, previous, reminder_service)
        elif action == "kind" and step == "schedule" and value in ("once", "daily", "weekly"):
            await state.update_data(kind=value, date=None, weekday=None)
            target = {"once": "date", "daily": "confirm", "weekly": "weekday"}[value]
            await _prompt(message, state, target, reminder_service)
        elif action == "month" and step == "date":
            month = date.fromisoformat(value).replace(day=1)
            today = reminder_service.now().astimezone(TASHKENT).date()
            if not today.replace(day=1) <= month <= date(min(today.year + 100, 9999), 1, 1):
                raise ValueError("Boshqa oyni tanlang.")
            await _prompt(message, state, "date", reminder_service, month=month)
        elif action == "date" and step == "date":
            updated = data | {"date": date.fromisoformat(value).isoformat()}
            _spec(updated).next_after(reminder_service.now())
            await state.update_data(date=updated["date"])
            await _prompt(message, state, "confirm", reminder_service)
        elif action == "weekday" and step == "weekday":
            updated = data | {"weekday": int(value)}
            _spec(updated)
            await state.update_data(weekday=updated["weekday"])
            await _prompt(message, state, "confirm", reminder_service)
        elif action == "save" and step == "confirm":
            await reminder_service.create(
                data["user_id"], message.chat.id, _spec(data), data["creation_token"]
            )
            await state.clear()
            await message.answer("✅ Eslatma qo‘shildi.", reply_markup=build_reminders_menu())
        else:
            raise ValueError("Joriy bosqichdagi tugmadan foydalaning.")
    except (ValueError, OverflowError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()


async def _show_list(
    message: Message, owner: int, page: int, services: HandlerServices, reminders: ReminderService
) -> None:
    user = await services.subscriptions.get(owner)
    assert user.id is not None
    rows, more = await reminders.page(user.id, page)
    statuses = {
        "active": "Faol",
        "processing": "Yuborilmoqda",
        "completed": "Bajarilgan",
        "failed": "Yuborilmadi",
        "paused": "To‘xtatilgan",
    }
    chunks = ["📋 Eslatma ro‘yxati\n\n"]
    if not rows:
        chunks[0] += "Hozircha eslatmalaringiz yo‘q." if not page else "Bu sahifada eslatma yo‘q."
    for i, row in enumerate(rows, 1):
        entry = (
            f"{page * 3 + i}. {row.spec.text}\n"
            f"🕒 {row.spec.at:%H:%M} · {row.spec.schedule_label()}\n"
            f"{statuses[row.status]}"
        )
        if len((chunks[-1] + entry).encode("utf-16-le")) // 2 > 3900:
            chunks.append("")
        chunks[-1] += entry + "\n\n"
    for index, text in enumerate(chunks):
        markup = page_keyboard(owner, page, more) if index == len(chunks) - 1 else None
        await message.answer(text.rstrip(), reply_markup=markup, parse_mode=None)


async def show_list(
    message: Message,
    state: FSMContext,
    handler_services: HandlerServices,
    reminder_service: ReminderService,
) -> None:
    await state.clear()
    if not await _private(message) or message.from_user is None:
        return
    await handler_services.subscriptions.start(message.from_user.id, message.chat.id)
    await _show_list(message, message.from_user.id, 0, handler_services, reminder_service)


async def list_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    reminder_service: ReminderService,
) -> None:
    message = callback.message
    try:
        _, owner_text, page_text = (callback.data or "").split(":")
        owner, page = int(owner_text), int(page_text)
        if (
            not isinstance(message, Message)
            or message.chat.type != "private"
            or owner != callback.from_user.id
            or message.chat.id != owner
            or not 0 <= page <= 1_000_000
        ):
            raise ValueError
    except ValueError:
        await callback.answer("So‘rov noto‘g‘ri.", show_alert=True)
        return
    if await state.get_state() is not None:
        await callback.answer("Avval joriy eslatmani saqlang yoki bekor qiling.", show_alert=True)
        return
    await _show_list(message, owner, page, handler_services, reminder_service)
    await callback.answer()


async def choose_button(message: Message) -> None:
    await message.answer("Davom etish uchun joriy xabardagi tugmani tanlang.")


def build_reminder_router() -> Router:
    router = Router(name="reminders")
    router.message.register(
        show_section, F.text.in_({PRAYER_MENU_LABEL, REMINDERS_LABEL, HOME_LABEL})
    )
    router.message.register(start_reminder, F.text == ADD_LABEL)
    router.message.register(show_list, F.text == LIST_LABEL)
    router.message.register(show_section, F.text.startswith("/"))
    router.message.register(receive_text, ReminderStates.text)
    router.message.register(receive_time, ReminderStates.time)
    for step in (
        ReminderStates.schedule,
        ReminderStates.date,
        ReminderStates.weekday,
        ReminderStates.confirm,
    ):
        router.message.register(choose_button, step)
    router.callback_query.register(dialog_callback, F.data.startswith("rem:"))
    router.callback_query.register(list_callback, F.data.startswith("remlist:"))
    return router
