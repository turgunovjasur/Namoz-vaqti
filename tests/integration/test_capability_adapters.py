from sqlalchemy import select

from namoz_bot.application.capabilities.registry import (
    CapabilityDispatcher,
    build_capability_registry,
)
from namoz_bot.application.main_agent import MainAgent
from namoz_bot.infrastructure.orm import FinanceEntryRecord
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.helpers.roles import build_role_registry
from tests.integration.test_agent_sessions import store  # noqa: F401
from tests.integration.test_voice_agent_actions import NOW, command
from tests.integration.test_voice_agent_actions import voice_agent as _fixture

voice_agent = _fixture


def capability_agent(agent):
    main, extractor, repo, _, _, _ = agent
    capabilities = build_capability_registry(main._adapters)
    roles = build_role_registry(capabilities)
    runtime = MainAgent(
        extractor,
        repo,
        adapters=CapabilityDispatcher(roles, capabilities),
        now=lambda: NOW,
        voice_first=True,
    )
    return (runtime, *agent[1:])


async def test_capability_expense_preserves_owner_and_replays_receipt(voice_agent):
    agent = capability_agent(voice_agent)
    parameters = {"amount": 120000, "currency": "UZS", "category": "kiyim", "description": "Kiyim"}
    first = await command(agent, "accounting", "expense", parameters, key="expense")
    assert first.status == "done" and first.effect == "committed"
    assert first.data["amount"] == 120000
    repeated = await command(
        agent, "accounting", "expense", {**parameters, "amount": 999}, key="expense"
    )
    assert repeated == first
    async with agent[3]() as session:
        rows = list(await session.scalars(select(FinanceEntryRecord)))
    assert len(rows) == 1 and rows[0].user_id == agent[4].user_id
    assert rows[0].amount == 120000
    assert (await agent[2].get_receipt(agent[4].user_id, "expense", NOW)).effect == "committed"


async def test_capability_reminder_keeps_explicit_confirmation(voice_agent):
    agent = capability_agent(voice_agent)
    pending = await command(
        agent, "reminder", "create", {"text": "Kitob", "time": "09:00", "kind": "daily"}
    )
    reminders = voice_agent[0]._adapters._reminders
    assert pending.status == "needs_confirmation"
    assert not (await reminders.page(agent[4].user_id, 0))[0]
    saved = await agent[0].confirm(
        context=agent[4],
        request_id="save",
        operation_id=pending.operation_id,
        revision=pending.data["revision"],
    )
    assert saved.effect == "committed"
    rows = (await reminders.page(agent[4].user_id, 0))[0]
    assert len(rows) == 1 and rows[0].spec.text == "Kitob"


async def test_preference_and_interval_adapters_use_same_transaction_services(voice_agent):
    agent = capability_agent(voice_agent)
    offset = await command(
        agent, "prayer", "set_offset", {"prayer": "shom", "minutes": 4, "mode": "set"}
    )
    interval = await command(agent, "nasihat", "set_interval", {"hours": 6}, key="interval")
    assert offset.effect == "committed" and interval.effect == "committed"
    users = SqlAlchemySubscriptionRepository(agent[3])
    assert (await users.get_by_telegram_user_id(7)).offsets.shom == 4
    assert (await users.get_by_telegram_user_id(8)).offsets.shom == 0
    for domain, action in [("prayer", "open_settings"), ("settings", "open")]:
        result = await command(agent, domain, action, {"view": "region"}, key=domain)
        assert result.status == "done" and "Toshkent" in result.data["text"]
