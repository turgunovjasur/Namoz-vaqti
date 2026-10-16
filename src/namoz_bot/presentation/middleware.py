"""Request-scoped service injection over short-transaction repositories."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.daily_schedule import DailyScheduleSettingsService
from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.religious_reminders import (
    ReligiousIntervalService,
    ReligiousReminderService,
)
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.authorization import access_context, require_operation
from namoz_bot.domain.models import UserSubscription
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from namoz_bot.presentation.handlers import RELIGIOUS_COOLDOWN_ID, HandlerServices
from namoz_bot.presentation.keyboards import (
    DAILY_SCHEDULE_LABEL,
    HELP_LABEL,
    OFFSETS_LABEL,
    PROFILE_LABEL,
    REGION_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    RELIGIOUS_REMINDER_LABEL,
    SETTINGS_LABEL,
    TODAY_LABEL,
    menu_visibility,
)
from namoz_bot.presentation.main_agent import MENU_MODE_KEY, NAVIGATION, legacy_menu_input
from namoz_bot.presentation.reminder_panel import APPEND_RESULTS, KEEP_MAIN_MENU, discard_panel

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseMiddleware):
    """Log update failures and return a safe Uzbek response to the user."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except AccessDenied as exc:
            target = event.message if isinstance(event, CallbackQuery) else event
            if isinstance(target, Message):
                await target.answer(str(exc), parse_mode=None)
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None
        except Exception as exc:
            # Provider/database exception strings can contain private request parameters.
            logger.error("telegram_update_failed error=%s", type(exc).__name__)
            message = getattr(event, "message", None)
            answer_target = message if message is not None else event
            answer = getattr(answer_target, "answer", None)
            if callable(answer):
                await answer(
                    "Vaqtincha xatolik yuz berdi. Iltimos, birozdan keyin qayta urinib ko‘ring."
                )
            callback_answer = getattr(event, "answer", None)
            if message is not None and callable(callback_answer):
                await callback_answer()
            return None


class ServicesMiddleware(BaseMiddleware):
    """Create one database transaction and service bundle per update."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        schedule_service: ScheduleService,
        *,
        timezone: str,
        religious_reminders: ReligiousReminderService | None = None,
        religious_intervals: ReligiousIntervalService | None = None,
        daily_settings: DailyScheduleSettingsService | None = None,
        main_agent: MainAgent | None = None,
        access: AccessService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._schedule_service = schedule_service
        self._timezone = ZoneInfo(timezone)
        self._religious_reminders = religious_reminders
        self._religious_intervals = religious_intervals
        self._daily_settings = daily_settings
        self._main_agent = main_agent
        self._access = access

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if self._access is not None:
            async with self._access.role_scope():
                return await self._dispatch(handler, event, data)
        return await self._dispatch(handler, event, data)

    async def _dispatch(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if self._access is not None:
            target = event.message if isinstance(event, CallbackQuery) else event
            sender = getattr(event, "from_user", None)
            if (
                not isinstance(target, Message)
                or target.chat.type != "private"
                or sender is None
                or target.chat.id != sender.id
            ):
                if (
                    isinstance(target, Message)
                    and target.chat.type != "private"
                    and self._main_agent is None
                ):
                    await target.answer("Botdan shaxsiy chat orqali foydalaning.", parse_mode=None)
                if isinstance(event, CallbackQuery):
                    await event.answer("Bu amal sizga tegishli emas.", show_alert=True)
                return None
            user, _ = await SqlAlchemySubscriptionRepository(self._session_factory).upsert_start(
                UserSubscription(sender.id, target.chat.id, "Toshkent", True)
            )
            assert user.id is not None
            from namoz_bot.infrastructure.admin_web.queries import sync_identity

            await sync_identity(self._session_factory, user.id, sender.full_name, sender.username)
            with access_context(self._access, user_id=user.id, telegram_user_id=sender.id):
                capability = manual_capability(event)
                if capability:
                    await require_operation(capability)
                roles = await self._access.available_roles(user.id)
                visible = {r.id for r in roles}
                visible.update(
                    route.domain
                    for r in roles
                    for c in r.capability_ids
                    for route in self._access.roles.capabilities.get(c).spec.routes
                )
                if "finance" in visible:
                    visible.add("accounting")
                with menu_visibility(frozenset(visible)):
                    result = await self._handle(handler, event, data)
                if capability:
                    await require_operation(capability)
                return result
        return await self._handle(handler, event, data)

    async def _handle(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        hybrid = self._main_agent is not None and self._main_agent.voice_first
        data["hybrid_menu"] = hybrid
        menu_mode = hybrid or bool(
            isinstance(state, FSMContext) and (await state.get_data()).get(MENU_MODE_KEY)
        )
        data[MENU_MODE_KEY] = menu_mode
        preserve_menu_mode = menu_mode and (
            (isinstance(event, CallbackQuery) and not (event.data or "").startswith("ag:"))
            or (isinstance(event, Message) and legacy_menu_input(event, data.get("raw_state")))
        )
        if self._main_agent is not None and not self._main_agent.voice_first:
            navigation = isinstance(event, Message) and event.text in NAVIGATION - {PROFILE_LABEL}
            callback_navigation = (
                isinstance(event, CallbackQuery)
                and event.data is not None
                and not event.data.startswith(("ag:", "pf:"))
                and ":undo:" not in event.data
            )
            target = event.message if isinstance(event, CallbackQuery) else event
            sender = getattr(event, "from_user", None)
            if (
                (navigation or callback_navigation)
                and isinstance(target, Message)
                and target.chat.type == "private"
                and sender is not None
                and target.chat.id == sender.id
            ):
                user = await SqlAlchemySubscriptionRepository(
                    self._session_factory,
                ).get_by_telegram_user_id(sender.id)
                if (
                    user
                    and user.id
                    and await self._main_agent.has_pending(
                        user.id,
                        datetime.now(self._timezone),
                    )
                ):
                    text = "Tugallanmagan vazifa bor. «Davom et» yoki «Bekor qil» deb yozing."
                    if isinstance(event, CallbackQuery):
                        await event.answer(text, show_alert=True)
                    else:
                        await target.answer(text)
                    return None
        if (
            isinstance(event, Message)
            and isinstance(state, FSMContext)
            and event.text
            and (
                event.text.startswith("/")
                or event.text
                in {
                    TODAY_LABEL,
                    PROFILE_LABEL,
                    menu_visibility,
                    REGION_LABEL,
                    OFFSETS_LABEL,
                    HELP_LABEL,
                    RELIGIOUS_REMINDER_LABEL,
                    RELIGIOUS_INTERVAL_LABEL,
                    SETTINGS_LABEL,
                    DAILY_SCHEDULE_LABEL,
                }
            )
        ):
            wait_id = (
                (await state.get_data()).get(RELIGIOUS_COOLDOWN_ID)
                if event.text == RELIGIOUS_REMINDER_LABEL
                else None
            )
            await discard_panel(event, state)
            await state.clear()
            if wait_id is not None:
                await state.update_data({RELIGIOUS_COOLDOWN_ID: wait_id})
            data["raw_state"] = None
        data["reminder_service"] = ReminderService(
            SqlAlchemyReminderRepository(self._session_factory)
        )
        data["handler_services"] = HandlerServices(
            subscriptions=SubscriptionService(
                SqlAlchemySubscriptionRepository(self._session_factory)
            ),
            schedules=self._schedule_service,
            today=lambda: datetime.now(self._timezone).date(),
            religious_reminders=self._religious_reminders,
            religious_intervals=self._religious_intervals,
            daily_settings=self._daily_settings,
        )
        if hybrid and isinstance(state, FSMContext):
            await state.update_data(
                {MENU_MODE_KEY: True, KEEP_MAIN_MENU: True, APPEND_RESULTS: True}
            )
        try:
            return await handler(event, data)
        finally:
            # Manual handlers clear their drafts independently of the explicit UI choice.
            if preserve_menu_mode and isinstance(state, FSMContext):
                await state.update_data({MENU_MODE_KEY: True})


def manual_capability(event: TelegramObject) -> str | None:
    if isinstance(event, Message):
        return {
            TODAY_LABEL: "prayer.schedule",
            "/today": "prayer.schedule",
            REGION_LABEL: "preferences.region_view",
            "/settings": "preferences.region_view",
            OFFSETS_LABEL: "preferences.offsets_view",
            "/offsets": "preferences.offsets_view",
            RELIGIOUS_REMINDER_LABEL: "nasihat.excerpt",
            RELIGIOUS_INTERVAL_LABEL: "nasihat.settings_view",
            DAILY_SCHEDULE_LABEL: "settings.open",
        }.get(event.text or "")
    if isinstance(event, CallbackQuery):
        prefix = (event.data or "").split(":")[0]
        return {
            "region": "prayer.set_region",
            "region-group": "preferences.region_view",
            "region-groups": "preferences.region_view",
            "offset": "preferences.offsets_view",
            "offsets": "preferences.offsets_view",
            "offset-change": "prayer.set_offset",
            "offset-schedule": "prayer.schedule",
            "nasihat": "nasihat.set_interval",
            "daily": "settings.set_daily",
        }.get(prefix)
    return None
