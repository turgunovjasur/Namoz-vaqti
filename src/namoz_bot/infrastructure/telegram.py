"""Rate-limited Telegram message-sending adapter."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterator
from typing import Protocol

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.domain.workforce.tasks import TaskMessage


def message_chunks(text: str) -> Iterator[str]:
    """Deliver complete plain text within a conservative UTF-16 message budget."""
    if not text:
        yield text
        return
    start = 0
    while start < len(text):
        end = start
        units = 0
        last_space = start
        while end < len(text):
            width = 2 if ord(text[end]) > 0xFFFF else 1
            if units + width > 4000:
                break
            units += width
            end += 1
            if text[end - 1].isspace():
                last_space = end
        if end < len(text) and last_space > start:
            end = last_space
        yield text[start:end]
        start = end


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
        for chunk in message_chunks(text):
            await self._send_chunk(chat_id, chunk)

    async def _send_chunk(self, chat_id: int, text: str) -> None:
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

    async def deliver_task(self, chat_id: int, message: TaskMessage) -> int | None:
        message_id = None
        chunks = [message.text[i : i + 4000] for i in range(0, len(message.text), 4000)]
        for index, text in enumerate(chunks):
            await self._rate_limiter.acquire()
            try:
                sent = await self._bot.send_message(
                    chat_id,
                    text,
                    parse_mode=None,
                    reply_markup=task_markup(message) if index == len(chunks) - 1 else None,
                )
                message_id = sent.message_id
            except TelegramForbiddenError as exc:
                raise RecipientBlockedError("Recipient blocked") from exc
        return message_id

    async def delete_task_message(self, chat_id: int, message_id: int) -> None:
        await self._rate_limiter.acquire()
        try:
            await self._bot.delete_message(chat_id, message_id)
        except TelegramBadRequest as exc:
            if not any(
                marker in str(exc).lower()
                for marker in (
                    "message to delete not found",
                    "message can’t be deleted",
                    "message can't be deleted",
                )
            ):
                raise
        except TelegramForbiddenError as exc:
            raise RecipientBlockedError("Recipient blocked") from exc

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


def task_markup(message: TaskMessage) -> InlineKeyboardMarkup | None:
    if not message.buttons or not message.task_id or message.revision is None:
        return None
    prefix = "wf" if message.buttons == "approval" else "wff"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha", callback_data=f"{prefix}:{message.task_id}:{message.revision}:y"
                ),
                InlineKeyboardButton(
                    text="❌ Yo‘q", callback_data=f"{prefix}:{message.task_id}:{message.revision}:n"
                ),
            ]
        ]
    )
