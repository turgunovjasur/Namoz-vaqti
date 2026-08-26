from typing import Any, cast

import pytest
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.methods import SendMessage

from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.infrastructure.telegram import TelegramMessageSender, TelegramRateLimiter


async def no_sleep(_seconds: float) -> None:
    return None


class FakeBot:
    def __init__(self, failures: list[Exception] | None = None) -> None:
        self.failures = list(failures or [])
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_kwargs: Any) -> None:
        self.calls.append((chat_id, text))
        if self.failures:
            raise self.failures.pop(0)


class FakeLimiter:
    def __init__(self) -> None:
        self.calls = 0

    async def acquire(self) -> None:
        self.calls += 1


async def test_sender_translates_forbidden_recipient() -> None:
    method = SendMessage(chat_id=10, text="jadval")
    bot = FakeBot([TelegramForbiddenError(method, "bot was blocked")])

    with pytest.raises(RecipientBlockedError):
        await TelegramMessageSender(cast(Bot, bot)).send(10, "jadval")


async def test_sender_retries_multiple_rate_limits_with_shared_limiter() -> None:
    method = SendMessage(chat_id=10, text="jadval")
    bot = FakeBot(
        [
            TelegramRetryAfter(method, "retry", retry_after=3),
            TelegramRetryAfter(method, "retry", retry_after=2),
        ]
    )
    limiter = FakeLimiter()

    await TelegramMessageSender(
        cast(Bot, bot),
        sleep=no_sleep,
        rate_limiter=limiter,
        max_attempts=3,
    ).send(10, "jadval")

    assert bot.calls == [(10, "jadval"), (10, "jadval"), (10, "jadval")]
    assert limiter.calls == 3


async def test_sender_retries_transient_network_failure() -> None:
    method = SendMessage(chat_id=10, text="jadval")
    bot = FakeBot([TelegramNetworkError(method, "connection reset")])

    await TelegramMessageSender(
        cast(Bot, bot),
        sleep=no_sleep,
        rate_limiter=FakeLimiter(),
    ).send(10, "jadval")

    assert len(bot.calls) == 2


async def test_sender_translates_permanent_missing_chat() -> None:
    method = SendMessage(chat_id=10, text="jadval")
    bot = FakeBot([TelegramBadRequest(method, "Bad Request: chat not found")])

    with pytest.raises(RecipientBlockedError):
        await TelegramMessageSender(
            cast(Bot, bot),
            rate_limiter=FakeLimiter(),
        ).send(10, "jadval")


async def test_rate_limiter_spaces_consecutive_permits() -> None:
    now = 100.0
    sleeps: list[float] = []

    async def advance(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    limiter = TelegramRateLimiter(
        messages_per_second=25,
        sleep=advance,
        clock=lambda: now,
    )

    await limiter.acquire()
    await limiter.acquire()

    assert sleeps == [pytest.approx(0.04)]
