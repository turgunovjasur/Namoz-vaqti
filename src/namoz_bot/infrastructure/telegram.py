"""Rate-limited Telegram message-sending adapter."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

from namoz_bot.domain.errors import RecipientBlockedError


class RateLimiter(Protocol):
    """Process-wide asynchronous send-rate boundary."""

    async def acquire(self) -> None: ...


class TelegramRateLimiter:
    """Serialize permits at a conservative Bot API message rate."""

    def __init__(
        self,
        *,
        messages_per_second: float = 25.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if messages_per_second <= 0:
            raise ValueError("messages_per_second musbat bo‘lishi kerak")
        self._interval = 1.0 / messages_per_second
        self._sleep = sleep
        self._clock = clock
        self._next_permit = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            wait_for = max(0.0, self._next_permit - now)
            if wait_for:
                await self._sleep(wait_for)
            self._next_permit = max(now, self._next_permit) + self._interval


class TelegramMessageSender:
    """Send with shared throttling and normalize permanent recipient failures."""

    def __init__(
        self,
        bot: Bot,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rate_limiter: RateLimiter | None = None,
        max_attempts: int = 3,
        retry_delays: tuple[float, ...] = (0.5, 1.5),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts kamida 1 bo‘lishi kerak")
        self._bot = bot
        self._sleep = sleep
        self._rate_limiter = rate_limiter or TelegramRateLimiter(sleep=sleep)
        self._max_attempts = max_attempts
        self._retry_delays = retry_delays

    async def send(self, chat_id: int, text: str) -> None:
        for attempt in range(self._max_attempts):
            await self._rate_limiter.acquire()
            try:
                await self._bot.send_message(chat_id, text)
                return
            except TelegramForbiddenError as exc:
                raise RecipientBlockedError("Telegram foydalanuvchisi botni bloklagan") from exc
            except TelegramBadRequest as exc:
                if self._is_permanent_recipient_error(exc):
                    raise RecipientBlockedError("Telegram chat endi xabar qabul qilmaydi") from exc
                raise
            except TelegramRetryAfter as exc:
                if attempt == self._max_attempts - 1:
                    raise
                await self._sleep(float(exc.retry_after))
            except (TelegramNetworkError, TelegramServerError):
                if attempt == self._max_attempts - 1:
                    raise
                delay_index = min(attempt, len(self._retry_delays) - 1)
                delay = self._retry_delays[delay_index] if self._retry_delays else 0.0
                await self._sleep(delay)

    @staticmethod
    def _is_permanent_recipient_error(exc: TelegramBadRequest) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "chat not found",
                "user is deactivated",
                "bot was blocked",
            )
        )
