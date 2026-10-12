import asyncio
import importlib

import pytest

from namoz_bot.domain.errors import ExternalServiceError, RecipientBlockedError
from namoz_bot.domain.models import UserSubscription


def user(identifier):
    return UserSubscription(
        id=identifier,
        telegram_user_id=identifier,
        chat_id=identifier * 10,
        region_code="Toshkent",
        is_active=True,
    )


class Subscriptions:
    def __init__(self, users):
        self.users = {item.telegram_user_id: item for item in users}

    async def set_active(self, telegram_user_id, active):
        item = self.users[telegram_user_id].with_preferences(is_active=active)
        self.users[telegram_user_id] = item
        return item

    async def list_active_page(self, *, after_id, limit):
        items = sorted(
            (item for item in self.users.values() if item.is_active and item.id > after_id),
            key=lambda item: item.id,
        )
        return items[:limit]


class Sender:
    def __init__(self, blocked_chat_id=None):
        self.blocked_chat_id = blocked_chat_id
        self.messages = []

    async def send(self, chat_id, text):
        if chat_id == self.blocked_chat_id:
            raise RecipientBlockedError("blocked")
        self.messages.append((chat_id, text))


class ReligiousProvider:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    async def generate(self):
        self.calls += 1
        if self.fail:
            raise ExternalServiceError("Gemini unavailable")
        return f"Sabrli bo‘ling. Yaxshilik qiling. {self.calls}"


def service(subscriptions, provider, sender, **kwargs):
    try:
        module = importlib.import_module("namoz_bot.application.religious_reminders")
    except ModuleNotFoundError:
        pytest.fail("Automatic religious broadcast is missing")
    return module.ReligiousBroadcastService(subscriptions, provider, sender, **kwargs)


async def test_one_generation_reaches_all_active_pages_and_next_run_generates_again():
    subscriptions = Subscriptions([user(1), user(2), user(3), user(4)])
    await subscriptions.set_active(3, False)
    provider = ReligiousProvider()
    sender = Sender()
    broadcaster = service(subscriptions, provider, sender, batch_size=2)

    first = await broadcaster.send()
    assert first.sent == 3
    assert [chat_id for chat_id, _ in sender.messages] == [10, 20, 40]
    assert {text for _, text in sender.messages} == {
        "📖 Diniy eslatma\n\nSabrli bo‘ling. Yaxshilik qiling. 1"
    }
    second = await broadcaster.send()
    assert second.sent == 3
    assert len(sender.messages) == 6
    assert provider.calls == 2
    assert "Yaxshilik qiling. 2" in sender.messages[-1][1]


async def test_empty_audience_does_not_call_gemini():
    provider = ReligiousProvider()
    sender = Sender()

    report = await service(Subscriptions([]), provider, sender).send()

    assert provider.calls == 0
    assert sender.messages == []
    assert report.sent == 0


async def test_gemini_failure_sends_nothing_and_next_interval_can_retry():
    provider = ReligiousProvider(fail=True)
    sender = Sender()
    broadcaster = service(Subscriptions([user(1)]), provider, sender)

    with pytest.raises(ExternalServiceError):
        await broadcaster.send()
    assert sender.messages == []
    provider.fail = False
    report = await broadcaster.send()
    assert report.sent == 1


async def test_blocked_chat_is_deactivated_and_other_users_receive_nasihat():
    subscriptions = Subscriptions([user(1), user(2)])
    sender = Sender(blocked_chat_id=10)

    report = await service(subscriptions, ReligiousProvider(), sender, batch_size=1).send()

    assert report.deactivated == 1
    assert report.sent == 1
    assert subscriptions.users[1].is_active is False
    assert [chat_id for chat_id, _ in sender.messages] == [20]


async def test_failed_send_does_not_stop_later_pages():
    class FailingSender(Sender):
        async def send(self, chat_id, text):
            if chat_id == 10:
                raise RuntimeError("Telegram unavailable")
            await super().send(chat_id, text)

    sender = FailingSender()
    report = await service(
        Subscriptions([user(1), user(2)]), ReligiousProvider(), sender, batch_size=1
    ).send()

    assert report.failed == 1
    assert report.sent == 1
    assert [chat_id for chat_id, _ in sender.messages] == [20]


async def test_broadcast_respects_configured_concurrency():
    class CountingSender(Sender):
        in_flight = 0
        peak = 0

        async def send(self, chat_id, text):
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            await asyncio.sleep(0)
            await super().send(chat_id, text)
            self.in_flight -= 1

    sender = CountingSender()
    report = await service(
        Subscriptions([user(i) for i in range(1, 6)]),
        ReligiousProvider(),
        sender,
        max_concurrency=2,
    ).send()

    assert report.sent == 5
    assert sender.peak == 2
