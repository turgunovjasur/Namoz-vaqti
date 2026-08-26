"""Telegram message-sending adapter."""

import asyncio
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from namoz_bot.domain.errors import RecipientBlockedError


class TelegramMessageSender:
    """Send messages and normalize Telegram delivery failures."""

    def __init__(
        self,
        bot: Bot,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._bot = bot
        self._sleep = sleep

    async def send(self, chat_id: int, text: str) -> None:
        try:
            await self._bot.send_message(chat_id, text)
        except TelegramForbiddenError as exc:
            raise RecipientBlockedError("Telegram foydalanuvchisi botni bloklagan") from exc
        except TelegramRetryAfter as exc:
            await self._sleep(float(exc.retry_after))
            try:
                await self._bot.send_message(chat_id, text)
            except TelegramForbiddenError as retry_exc:
                raise RecipientBlockedError(
                    "Telegram foydalanuvchisi botni bloklagan"
                ) from retry_exc
