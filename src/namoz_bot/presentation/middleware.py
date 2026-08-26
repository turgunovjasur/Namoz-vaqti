"""Request-scoped service injection over short-transaction repositories."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from namoz_bot.presentation.handlers import HandlerServices

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
    ) -> None:
        self._session_factory = session_factory
        self._schedule_service = schedule_service
        self._timezone = ZoneInfo(timezone)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["handler_services"] = HandlerServices(
            subscriptions=SubscriptionService(
                SqlAlchemySubscriptionRepository(self._session_factory)
            ),
            schedules=self._schedule_service,
            today=lambda: datetime.now(self._timezone).date(),
        )
        return await handler(event, data)
