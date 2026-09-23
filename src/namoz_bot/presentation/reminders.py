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
)
from namoz_bot.presentation.reminder_keyboards import (
    delete_keyboard,
    dialog_keyboard,
    menu_keyboard,
    page_keyboard,
)
from namoz_bot.presentation.reminder_panel import (
    PANEL_ID,
    delete_input,
    discard_panel,
    render_panel,
    reset_draft,
)


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
        tuple(data.get("weekdays", [])),
    )


async def _private(message: Message) -> bool:
    if message.chat.type != "private":
        await message.answer("Eslatmalarni bot bilan shaxsiy chatda oching.")
        return False
    return True


async def show_section(message: Message, state: FSMContext) -> None:
    if message.text == REMINDERS_LABEL:
        if await _private(message) and message.from_user is not None:
            await reset_draft(state)
            await render_panel(
                message,
                state,
                "🔔 Eslatmalar. Amalni tanlang:",
                menu_keyboard(message.from_user.id, section=True),
            )
            await delete_input(message)
        return
    await discard_panel(message, state)
    await state.clear()
    if message.text == PRAYER_MENU_LABEL:
        await message.answer("🕌 Namoz vaqti. Amalni tanlang:", reply_markup=build_prayer_menu())
    else:
        await message.answer("Asosiy menyu. Bo‘limni tanlang:", reply_markup=build_main_menu())


async def _prompt(
    message: Message,
    state: FSMContext,
    step: str,
    service: ReminderService,
    month: date | None = None,
    error: str | None = None,
) -> None:
    data = await state.get_data()
    # Queued taps from the same weekday grid must all update the selection.
    # Rotate on leaving/re-entering the step so retired grids stay invalid.
    token = (
        data["token"] if step == "weekday" and data.get("step") == "weekday" else uuid4().hex[:16]
    )
    await state.update_data(token=token, step=step)
    await state.set_state(getattr(ReminderStates, step))
    today = service.now().astimezone(TASHKENT).date()
    prompts = {
        "text": "Eslatma matnini yozing (1–1000 belgi):",
        "time": "Soat nechada eslatay? HH:MM shaklida kiriting.\nToshkent vaqti bo‘yicha.",
        "schedule": "Qachon eslatay?",
        "date": "Sanani tanlang:",
        "weekday": "Qaysi kunlarda takrorlansin?",
    }
    text = prompts.get(step, "")
    if step == "confirm":
        spec = _spec(data)
        text = f"📝 {spec.text}\n🕒 {spec.at:%H:%M} · Toshkent\n📅 {spec.schedule_label()}"
    if error:
        text = f"{error}\n\n{text}"
    await render_panel(
        message,
        state,
        text,
        dialog_keyboard(
            token,
            step,
            month=month or today.replace(day=1),
            today=today,
            weekdays=tuple(data.get("weekdays", [])),
        ),
    )


async def start_reminder(
    message: Message,
    state: FSMContext,
    reminder_service: ReminderService,
    handler_services: HandlerServices,
) -> None:
    await reset_draft(state)
    if not await _private(message) or message.from_user is None:
        return
    await _start_reminder(message, state, message.from_user.id, reminder_service, handler_services)
    await delete_input(message)


async def _start_reminder(
    message: Message,
    state: FSMContext,
    owner: int,
    reminder_service: ReminderService,
    handler_services: HandlerServices,
) -> None:
    user = await handler_services.subscriptions.start(owner, message.chat.id)
    await state.update_data(creation_token=uuid4().hex, user_id=user.subscription.id)
    await _prompt(message, state, "text", reminder_service)


async def receive_text(
    message: Message, state: FSMContext, reminder_service: ReminderService
) -> None:
    if not await _private(message):
        return
    value = (message.text or "").strip()
    if not 1 <= len(value) <= 1000:
        await _prompt(
            message,
            state,
            "text",
            reminder_service,
            error="Eslatma matni 1–1000 belgidan iborat bo‘lsin.",
        )
        await delete_input(message)
        return
    await state.update_data(text=value)
    await _prompt(message, state, "time", reminder_service)
    await delete_input(message)


async def receive_time(
    message: Message, state: FSMContext, reminder_service: ReminderService
) -> None:
    try:
        at = parse_time(message.text or "")
    except ValueError as exc:
        await _prompt(message, state, "time", reminder_service, error=str(exc))
        await delete_input(message)
        return
    await state.update_data(time=at.strftime("%H:%M"))
    await _prompt(message, state, "schedule", reminder_service)
    await delete_input(message)


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
        or data.get(PANEL_ID) != message.message_id
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
            await reset_draft(state)
            await render_panel(
                message,
                state,
                "Bekor qilindi. Eslatmalar menyusidan amalni tanlang.",
                menu_keyboard(callback.from_user.id),
            )
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
            await state.update_data(kind=value, date=None, weekdays=[])
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
            day = int(value)
            if not 0 <= day <= 6:
                raise ValueError("Hafta kuni noto‘g‘ri.")
            days = set(data.get("weekdays", []))
            days.symmetric_difference_update({day})
            await state.update_data(weekdays=sorted(days))
            await _prompt(message, state, "weekday", reminder_service)
        elif action == "continue" and step == "weekday":
            if not data.get("weekdays"):
                raise ValueError("Kamida bitta kunni tanlang.")
            await _prompt(message, state, "confirm", reminder_service)
        elif action == "save" and step == "confirm":
            await reminder_service.create(
                data["user_id"], message.chat.id, _spec(data), data["creation_token"]
            )
            await reset_draft(state)
            await render_panel(
                message, state, "✅ Eslatma qo‘shildi.", menu_keyboard(callback.from_user.id)
            )
        else:
            raise ValueError("Joriy bosqichdagi tugmadan foydalaning.")
    except (ValueError, OverflowError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()


async def _show_list(
    message: Message,
    state: FSMContext,
    owner: int,
    page: int,
    services: HandlerServices,
    reminders: ReminderService,
    part: int = 0,
) -> None:
    user = await services.subscriptions.get(owner)
    assert user.id is not None
    rows, more = await reminders.page(user.id, page)
    if not rows and page:
        page, part = 0, 0
        rows, more = await reminders.page(user.id, page)
    statuses = {
        "active": "Faol",
        "processing": "Yuborilmoqda",
        "completed": "Bajarilgan",
        "failed": "Yuborilmadi",
        "paused": "To‘xtatilgan",
    }
    chunks = ["📋 Eslatma ro‘yxati\n\n"]
    chunk_items: list[list[tuple[int, int]]] = [[]]
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
            chunk_items.append([])
        chunks[-1] += entry + "\n\n"
        chunk_items[-1].append((page * 3 + i, row.id))
    selected = len(chunks) - 1 if part == -1 else min(part, len(chunks) - 1)
    token = uuid4().hex[:16]
    await state.update_data(
        delete_token=token,
        delete_stage="list",
        delete_target=None,
        delete_ids=[item[1] for item in chunk_items[selected]],
        list_page=page,
        list_part=selected,
    )
    await render_panel(
        message,
        state,
        chunks[selected].rstrip(),
        page_keyboard(
            owner,
            page,
            more,
            part=selected,
            parts=len(chunks),
            delete_token=token,
            items=tuple(chunk_items[selected]),
        ),
    )


async def show_list(
    message: Message,
    state: FSMContext,
    handler_services: HandlerServices,
    reminder_service: ReminderService,
) -> None:
    await reset_draft(state)
    if not await _private(message) or message.from_user is None:
        return
    await handler_services.subscriptions.start(message.from_user.id, message.chat.id)
    await _show_list(message, state, message.from_user.id, 0, handler_services, reminder_service)
    await delete_input(message)


async def list_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    reminder_service: ReminderService,
) -> None:
    message = callback.message
    try:
        _, owner_text, page_text, part_text = (callback.data or "").split(":")
        owner, page, part = int(owner_text), int(page_text), int(part_text)
        if (
            not isinstance(message, Message)
            or message.chat.type != "private"
            or owner != callback.from_user.id
            or message.chat.id != owner
            or not 0 <= page <= 1_000_000
            or not -1 <= part <= 2
        ):
            raise ValueError
    except ValueError:
        await callback.answer("So‘rov noto‘g‘ri.", show_alert=True)
        return
    if await state.get_state() is not None:
        await callback.answer("Avval joriy eslatmani saqlang yoki bekor qiling.", show_alert=True)
        return
    data = await state.get_data()
    if data.get(PANEL_ID) != message.message_id:
        await callback.answer(
            "Bu ro‘yxat eskirgan. Eslatma ro‘yxatini qayta oching.", show_alert=True
        )
        return
    await state.update_data({PANEL_ID: message.message_id})
    await _show_list(message, state, owner, page, handler_services, reminder_service, part)
    await callback.answer()


async def choose_button(
    message: Message, state: FSMContext, reminder_service: ReminderService
) -> None:
    data = await state.get_data()
    await _prompt(
        message,
        state,
        data["step"],
        reminder_service,
        error="Davom etish uchun shu xabardagi tugmani tanlang.",
    )
    await delete_input(message)


async def delete_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    reminder_service: ReminderService,
) -> None:
    message = callback.message
    data = await state.get_data()
    parts = (callback.data or "").split(":")
    if (
        not isinstance(message, Message)
        or message.chat.type != "private"
        or message.chat.id != callback.from_user.id
        or data.get(PANEL_ID) != message.message_id
        or await state.get_state() is not None
        or len(parts) != 4
        or parts[1] != data.get("delete_token")
        or not parts[3].isascii()
        or not parts[3].isdigit()
        or len(parts[3]) > 19
    ):
        await callback.answer("Bu tugma eskirgan. Ro‘yxatni qayta oching.", show_alert=True)
        return
    action, reminder_id = parts[2], int(parts[3])
    if (
        action == "ask"
        and data.get("delete_stage") == "list"
        and reminder_id in data.get("delete_ids", [])
    ):
        user = await handler_services.subscriptions.get(callback.from_user.id)
        assert user.id is not None
        reminder = await reminder_service.get(user.id, reminder_id)
        if reminder is not None:
            token = uuid4().hex[:16]
            await state.update_data(
                delete_token=token, delete_stage="confirm", delete_target=reminder_id
            )
            await render_panel(
                message,
                state,
                f"Shu eslatma o‘chirilsinmi?\n\n📝 {reminder.spec.text}\n"
                f"🕒 {reminder.spec.at:%H:%M} · Toshkent\n📅 {reminder.spec.schedule_label()}",
                delete_keyboard(token, reminder_id),
            )
            await callback.answer()
            return
    elif (
        action in {"yes", "back"}
        and data.get("delete_stage") == "confirm"
        and reminder_id == data.get("delete_target")
    ):
        if action == "yes":
            user = await handler_services.subscriptions.get(callback.from_user.id)
            assert user.id is not None
            deleted = await reminder_service.delete(user.id, reminder_id)
            await callback.answer(
                "Eslatma o‘chirildi." if deleted else "Eslatma allaqachon o‘chirilgan."
            )
        else:
            await callback.answer()
    else:
        await callback.answer("Bu tugma eskirgan. Ro‘yxatni qayta oching.", show_alert=True)
        return
    await _show_list(
        message,
        state,
        callback.from_user.id,
        data["list_page"],
        handler_services,
        reminder_service,
        data["list_part"],
    )
    if action == "ask":
        await callback.answer("Eslatma topilmadi.")


async def menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    handler_services: HandlerServices,
    reminder_service: ReminderService,
) -> None:
    message = callback.message
    parts = (callback.data or "").split(":")
    data = await state.get_data()
    if (
        not isinstance(message, Message)
        or message.chat.type != "private"
        or len(parts) != 3
        or parts[1] != str(callback.from_user.id)
        or message.chat.id != callback.from_user.id
        or parts[2] not in {"menu", "list", "add", "home"}
        or data.get(PANEL_ID) != message.message_id
        or await state.get_state() is not None
    ):
        await callback.answer(
            "Bu tugma eskirgan. Joriy xabardagi tugmani tanlang.", show_alert=True
        )
        return
    action = parts[2]
    owner = callback.from_user.id
    await reset_draft(state)
    if action == "home":
        await discard_panel(message, state)
        await state.clear()
        await message.answer("Asosiy menyu. Bo‘limni tanlang:", reply_markup=build_main_menu())
    elif action == "menu":
        await render_panel(
            message, state, "🔔 Eslatmalar. Amalni tanlang:", menu_keyboard(owner, section=True)
        )
    elif action == "add":
        await _start_reminder(message, state, owner, reminder_service, handler_services)
    else:
        await handler_services.subscriptions.start(owner, message.chat.id)
        await _show_list(message, state, owner, 0, handler_services, reminder_service)
    await callback.answer()


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
    router.callback_query.register(menu_callback, F.data.startswith("remmenu:"))
    router.callback_query.register(delete_callback, F.data.startswith("remdel:"))
    return router
