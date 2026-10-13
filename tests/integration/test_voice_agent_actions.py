
import pytest
from pydantic import ValidationError

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.conversation_actions import ConversationAdapters
from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.reminders import ReminderService
from namoz_bot.domain.agent_protocol import AgentContext, AgentDecision, AgentRevisionConflict
from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository
from namoz_bot.infrastructure.agent_sessions import SqlAlchemyAgentTransaction
from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
from namoz_bot.infrastructure.religious_intervals import SqlAlchemyReligiousIntervalRepository
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.integration.test_agent_sessions import NOW, store  # noqa: F401
from tests.integration.test_main_agent_operations import Extractor


@pytest.fixture
def voice_agent(store):  # noqa: F811
    repo, factory, user, other = store
    extractor = Extractor()
    adapters = ConversationAdapters(
        reminders=ReminderService(SqlAlchemyReminderRepository(factory), now=lambda: NOW),
        ledger=LedgerService(SqlAlchemyLedgerRepository(factory)),
    )
    main = MainAgent(extractor, repo, adapters=adapters, now=lambda: NOW, voice_first=True)
    context = AgentContext(
        bot_id=123456,
        telegram_user_id=7,
        chat_id=7,
        user_id=user,
        message_time=NOW,
        region_code="Toshkent",
    )
    return main, extractor, repo, factory, context, other


async def command(agent, domain, action, parameters=None, key="one", text="test", audio=None):
    main, extractor, _, _, context, _ = agent
    extractor.decision = AgentDecision(
        domain=domain, action=action, parameters=parameters or {}, transcript=text
    )
    return await main.respond(
        context=context, request_id=key, text=None if audio else text, audio=audio
    )


@pytest.mark.parametrize(
    "domain,action,parameters",
    [
        ("settings", "set_daily", {"time": "25:00"}),
        ("nasihat", "set_interval", {"hours": -1}),
        ("nasihat", "set_interval", {"hours": 169}),
        ("nasihat", "set_interval", {"hours": True}),
        ("prayer", "set_offset", {"minutes": 31}),
    ],
)
def test_voice_setting_values_are_strict(domain, action, parameters):
    with pytest.raises(ValidationError):
        AgentDecision(domain=domain, action=action, parameters=parameters, transcript="test")


async def test_daily_time_is_saved_and_duplicate_does_not_move_due(voice_agent):
    output = await command(voice_agent, "settings", "set_daily", {"time": "07:00"})
    assert output.status == "done" and output.effect == "committed"
    assert "07:00" in output.data["text"]
    repository = SqlAlchemyDailyScheduleRepository(voice_agent[3])
    first = await repository.get(7)
    assert first.at.hour == 7 and first.at.minute == 0
    replay = await command(voice_agent, "settings", "set_daily", {"time": "09:00"})
    assert replay == output and (await repository.get(7)).next_due == first.next_due
    assert (await repository.get(7)).at.hour == 7


@pytest.mark.parametrize("hours", [0, 6, 168])
async def test_nasihat_interval_changes_without_menu(voice_agent, hours):
    result = await command(voice_agent, "nasihat", "set_interval", {"hours": hours})
    assert result.status == "done" and result.effect == "committed"
    item = await SqlAlchemyReligiousIntervalRepository(voice_agent[3]).get(7)
    assert item.interval_hours == hours
    assert (item.next_due is None) == (hours == 0)


async def test_region_change_and_offset_updates_are_owner_scoped(voice_agent):
    repository = SqlAlchemySubscriptionRepository(voice_agent[3])
    await command(
        voice_agent, "prayer", "set_offset", {"prayer": "shom", "minutes": 5, "mode": "add"}
    )
    assert (await repository.get_by_telegram_user_id(7)).offsets.shom == 5
    assert (await repository.get_by_telegram_user_id(8)).offsets.shom == 0
    result = await command(
        voice_agent, "prayer", "set_region", {"region": "Samarqand shahri"}, key="region"
    )
    assert result.status == "done" and result.effect == "committed"
    user = await repository.get_by_telegram_user_id(7)
    assert user.region_code == "Samarqand" and user.offsets.shom == 0
    assert (await repository.get_by_telegram_user_id(8)).region_code == "Toshkent"


async def test_ambiguous_region_asks_and_followup_saves(voice_agent):
    first = await command(voice_agent, "prayer", "set_region", {"region": "Andijon"})
    assert first.status == "needs_input"
    assert "shahri" in first.question and "tumani" in first.question
    result = await command(
        voice_agent, "prayer", "set_region", {"region": "Andijon shahri"}, key="followup"
    )
    assert result.effect == "committed"


async def test_preference_write_rolls_back_when_receipt_conflicts(voice_agent, monkeypatch):
    repository = SqlAlchemyDailyScheduleRepository(voice_agent[3])
    from datetime import time

    await repository.set_time(7, time(21), NOW)

    async def conflict(self, output):
        raise AgentRevisionConflict("synthetic duplicate receipt")

    monkeypatch.setattr(SqlAlchemyAgentTransaction, "save_receipt", conflict)
    result = await command(voice_agent, "settings", "set_daily", {"time": "07:00"})
    assert result.status == "error"
    assert (await repository.get(7)).at.hour == 21
    assert await voice_agent[2].get_receipt(voice_agent[4].user_id, "one", NOW) is None
