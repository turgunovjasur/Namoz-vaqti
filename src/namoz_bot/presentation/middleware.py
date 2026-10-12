"""Request-scoped service injection over short-transaction repositories."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.daily_schedule import DailyScheduleSettingsService
from namoz_bot.application.religious_reminders import (
    ReligiousIntervalService,
    ReligiousReminderService,
)
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from namoz_bot.presentation.handlers import RELIGIOUS_COOLDOWN_ID, HandlerServices
from namoz_bot.presentation.keyboards import (
    DAILY_SCHEDULE_LABEL,
    HELP_LABEL,
    OFFSETS_LABEL,
    REGION_LABEL,
    RELIGIOUS_INTERVAL_LABEL,
    RELIGIOUS_REMINDER_LABEL,
    SETTINGS_LABEL,
    TODAY_LABEL,
)
from namoz_bot.presentation.reminder_panel import discard_panel

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
        except Exception as exc:
            logger.exception("telegram_update_failed error=%s", type(exc).__name__)
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
    ) -> None:
        self._session_factory = session_factory
        self._schedule_service = schedule_service
        self._timezone = ZoneInfo(timezone)
        self._religious_reminders = religious_reminders
        self._religious_intervals = religious_intervals
        self._daily_settings = daily_settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        if (
            isinstance(event, Message)
            and isinstance(state, FSMContext)
            and event.text
            and (
                event.text.startswith("/")
                or event.text
                in {
                    TODAY_LABEL,
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
        return await handler(event, data)
