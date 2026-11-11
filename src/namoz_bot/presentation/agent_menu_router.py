"""Open granted agents and reuse manual skill interfaces by capability ID."""

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.authorization import selected_operation
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.presentation.accounting import (
    AccountingStates,
    _show_history,
    open_accounting,
    show_month,
)
from namoz_bot.presentation.accounting_menu import MONTH_KEY, current_month, keyboard
from namoz_bot.presentation.agent_menu_context import (
    ROLE_KEY,
    action_labels,
    agent_label,
    menu_roles,
    selected_role,
)
from namoz_bot.presentation.handlers import (
    HandlerServices,
    handle_offsets,
    handle_religious_reminder,
    handle_settings,
    handle_today,
)
from namoz_bot.presentation.keyboards import build_agent_actions_menu
from namoz_bot.presentation.religious_settings import show_interval
from namoz_bot.presentation.reminder_panel import KEEP_MAIN_MENU, discard_panel, render_panel
from namoz_bot.presentation.reminders import _show_list, start_reminder
from namoz_bot.presentation.settings import show_daily


class AgentMenuFilter(BaseFilter):
    async def __call__(self, message: Message) -> dict[str, str] | bool:
        for role in menu_roles() or ():
            if message.text in {agent_label(role), role.name}:
                return {"agent_menu_id": role.id}
        return False


class AgentActionFilter(BaseFilter):
    async def __call__(self, message: Message) -> dict[str, str] | bool:
        cap = action_labels().get(message.text or "")
        return {"agent_capability": cap} if cap else False


async def open_agent(
    message: Message,
    state: FSMContext,
    agent_menu_id: str,
    handler_services: HandlerServices,
    ledger_service: LedgerService,
) -> None:
    role = selected_role()
    if role is None or role.id != agent_menu_id:
        raise AccessDenied("Agent hozir siz uchun mavjud emas.")
    await discard_panel(message, state)
    await state.clear()
    await state.update_data({ROLE_KEY: role.id, KEEP_MAIN_MENU: True})
    actions = action_labels()
    if actions and all(c.startswith("finance.") for c in actions.values()):
        await open_accounting(message, state, handler_services, ledger_service)
        await state.update_data({ROLE_KEY: role.id})
        return
    await message.answer(
        f"{agent_label(role)}\n{role.description}\n\nAmalni tanlang.",
        reply_markup=build_agent_actions_menu(),
        parse_mode=None,
    )


async def agent_action(
    message: Message,
    state: FSMContext,
    agent_capability: str,
    handler_services: HandlerServices,
    ledger_service: LedgerService,
    reminder_service: ReminderService,
    access_service: AccessService,
) -> None:
    role = selected_role()
    if role is None or message.from_user is None:
        raise AccessDenied("Agentni qayta oching.")
    user = await handler_services.subscriptions.get(message.from_user.id)
    assert user.id is not None
    await access_service.require(user.id, role.id, agent_capability)
    month = (await state.get_data()).get(MONTH_KEY, current_month().isoformat())
    await discard_panel(message, state)
    await state.clear()
    await state.update_data({ROLE_KEY: role.id, KEEP_MAIN_MENU: True, MONTH_KEY: month})
    # Some screens show several independently authorized reads; execution still rechecks each one.
    cap = agent_capability
    if cap.startswith("finance."):
        await state.set_state(AccountingStates.active)
        if cap == "finance.report":
            await show_month(message, state, ledger_service, user.id)
        elif cap in {"finance.history", "finance.undo"}:
            if cap == "finance.undo" and "finance.history" not in role.capability_ids:
                await message.answer(
                    "Bekor qilinadigan yozuvni ayting: «Oxirgi yozuvni bekor qil»."
                )
            else:
                await _show_history(
                    message, state, ledger_service, user.id, message.from_user.id, 0
                )
        elif cap == "finance.balance":
            from namoz_bot.domain.accounting import format_money

            balance = await ledger_service.balance(user.id)
            await render_panel(
                message,
                state,
                f"💳 Umumiy balans: {format_money(balance)}",
                keyboard(message.from_user.id),
            )
        else:
            await state.set_state(AccountingStates.entry)
            await state.update_data(accounting_intent=cap.split(".")[1])
            await render_panel(
                message,
                state,
                "Summa va izohni yozing. Sana aytilmasa bugungi sana olinadi.",
                keyboard(message.from_user.id),
            )
        return
    with selected_operation(role.id, cap):
        if cap == "prayer.schedule":
            await handle_today(message, handler_services)
        elif cap in {"prayer.set_region", "preferences.region_view"}:
            await handle_settings(message, handler_services)
        elif cap in {"prayer.set_offset", "preferences.offsets_view"}:
            await handle_offsets(message, handler_services)
        elif cap in {"settings.open", "settings.set_daily"}:
            await show_daily(message, state, handler_services)
        elif cap == "nasihat.excerpt":
            await handle_religious_reminder(message, handler_services, state)
        elif cap in {"nasihat.settings_view", "nasihat.set_interval"}:
            await show_interval(message, handler_services, state)
        elif cap == "reminder.create":
            await start_reminder(message, state, reminder_service, handler_services)
        elif cap in {"reminder.list", "reminder.delete"}:
            await _show_list(
                message,
                state,
                message.from_user.id,
                0,
                handler_services,
                reminder_service,
                deleting=cap == "reminder.delete",
                today=message.text == "📅 Bugungi eslatmalar",
            )
        else:
            await message.answer(
                f"{role.name} uchun topshiriqni matn yoki ovoz bilan ayting.\n"
                f"Tanlangan amal: {message.text}",
                parse_mode=None,
            )


def build_agent_menu_router() -> Router:
    router = Router(name="agent-menus")
    router.message.filter(F.chat.type == "private")
    router.message.register(open_agent, AgentMenuFilter())
    router.message.register(agent_action, AgentActionFilter())
    return router
