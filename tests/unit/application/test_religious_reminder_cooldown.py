import asyncio
import importlib

import pytest

from namoz_bot.domain.errors import ExternalServiceError


class Provider:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.started = asyncio.Event()
        self.release = None

    async def generate(self):
        self.calls += 1
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.fail:
            raise ExternalServiceError("Gemini unavailable")
        return f"Nasihat {self.calls}"


def service(provider, clock, cooldown=60):
    try:
        module = importlib.import_module("namoz_bot.application.religious_reminders")
    except ModuleNotFoundError:
        pytest.fail("Button cooldown is missing")
    return module.ReligiousReminderService(provider, cooldown_seconds=cooldown, clock=clock)


async def test_repeated_press_is_rejected_until_cooldown_expires():
    now = [100.0]
    provider = Provider()
    reminders = service(provider, lambda: now[0])
    assert await reminders.generate(7) == "Nasihat 1"

    now[0] = 120.1
    with pytest.raises(Exception) as rejected:
        await reminders.generate(7)
    assert type(rejected.value).__name__ == "ReligiousReminderCooldownError"
    assert rejected.value.remaining_seconds == 40
    assert provider.calls == 1

    now[0] = 160.0
    assert await reminders.generate(7) == "Nasihat 2"
    assert provider.calls == 2


async def test_one_user_cooldown_does_not_block_another():
    provider = Provider()
    reminders = service(provider, lambda: 100.0)

    assert await reminders.generate(7) == "Nasihat 1"
    assert await reminders.generate(8) == "Nasihat 2"


async def test_in_flight_request_stays_blocked_even_after_cooldown_expires():
    now = [100.0]
    provider = Provider()
    provider.release = asyncio.Event()
    reminders = service(provider, lambda: now[0])
    first = asyncio.create_task(reminders.generate(7))
    try:
        await provider.started.wait()
        now[0] = 170.0
        with pytest.raises(Exception) as rejected:
            await reminders.generate(7)
        assert type(rejected.value).__name__ == "ReligiousReminderCooldownError"
        assert provider.calls == 1
    finally:
        provider.release.set()
        await first


async def test_gemini_error_preserves_cooldown_but_releases_in_flight_lock():
    now = [100.0]
    provider = Provider()
    provider.fail = True
    reminders = service(provider, lambda: now[0])
    with pytest.raises(ExternalServiceError):
        await reminders.generate(7)
    provider.fail = False
    with pytest.raises(Exception) as rejected:
        await reminders.generate(7)
    assert type(rejected.value).__name__ == "ReligiousReminderCooldownError"
    assert provider.calls == 1
    now[0] = 160.0
    assert await reminders.generate(7) == "Nasihat 2"
