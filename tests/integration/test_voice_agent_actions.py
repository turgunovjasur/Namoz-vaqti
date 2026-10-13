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


async def test_immediate_voice_confirmation_creates_once_and_replays(voice_agent):
    first = await command(
        voice_agent,
        "reminder",
        "create",
        {"text": "Kitob", "time": "09:00", "kind": "daily"},
        audio=b"OggS",
    )
    assert first.status == "needs_confirmation"
    assert not (await voice_agent[0]._adapters._reminders.page(voice_agent[4].user_id, 0))[0]
    saved = await command(
        voice_agent, "assistant", "confirm", key="yes", audio=b"OggS", text="Ha, saqla"
    )
    assert saved.status == "done" and saved.effect == "committed"
    repeated = await command(voice_agent, "assistant", "confirm", key="yes", audio=b"OggS")
    assert repeated == saved
    assert len((await voice_agent[0]._adapters._reminders.page(voice_agent[4].user_id, 0))[0]) == 1


async def test_voice_yes_to_partial_draft_does_not_save(voice_agent):
    await command(voice_agent, "reminder", "create", {"text": "Kitob"}, audio=b"OggS")
    result = await command(voice_agent, "assistant", "confirm", key="yes", audio=b"OggS")
    assert result.status == "needs_input" and "time" in result.missing_fields
    assert not (await voice_agent[0]._adapters._reminders.page(voice_agent[4].user_id, 0))[0]


async def test_delete_confirmation_cannot_touch_other_owner(voice_agent):
    from namoz_bot.domain.reminders import ReminderSpec, parse_time

    reminders = voice_agent[0]._adapters._reminders
    other = await reminders.create(
        voice_agent[5], 8, ReminderSpec("Other", parse_time("09:00"), "daily"), "other"
    )
    result = await command(voice_agent, "reminder", "delete", {"target_id": other.id})
    assert result.status == "unsupported"
    assert await reminders.get(voice_agent[5], other.id) is not None
    own = await reminders.create(
        voice_agent[4].user_id, 7, ReminderSpec("Kitob", parse_time("09:00"), "daily"), "own"
    )
    draft = await command(voice_agent, "reminder", "delete", {"text": "Kitob"}, key="delete")
    assert draft.status == "needs_confirmation"
    assert await reminders.get(voice_agent[4].user_id, own.id)
    deleted = await command(voice_agent, "assistant", "confirm", key="yes", text="ha")
    assert (
        deleted.effect == "committed"
        and await reminders.get(voice_agent[4].user_id, own.id) is None
    )
    assert await reminders.get(voice_agent[5], other.id)


async def test_ambiguous_reminder_title_is_not_guessed(voice_agent):
    from namoz_bot.domain.reminders import ReminderSpec, parse_time

    reminders = voice_agent[0]._adapters._reminders
    for number in range(2):
        await reminders.create(
            voice_agent[4].user_id,
            7,
            ReminderSpec("Kitob", parse_time("09:00"), "daily"),
            f"own:{number}",
        )
    result = await command(voice_agent, "reminder", "delete", {"text": "Kitob"})
    assert result.status == "needs_input" and "raqam" in result.question
    assert len((await reminders.page(voice_agent[4].user_id, 0))[0]) == 2


async def test_last_finance_entry_undo_requires_confirmation_and_is_idempotent(voice_agent):
    await command(
        voice_agent,
        "accounting",
        "expense",
        {"amount": 120000, "currency": "UZS", "category": "kiyim", "description": "Kiyim"},
    )
    prepared = await command(voice_agent, "accounting", "undo", key="undo")
    assert prepared.status == "needs_confirmation"
    ledger = voice_agent[0]._adapters._ledger
    assert await ledger.balance(voice_agent[4].user_id) == -120000
    output = await command(voice_agent, "assistant", "confirm", key="yes", text="ha")
    assert output.effect == "committed" and await ledger.balance(voice_agent[4].user_id) == 0
    assert await command(voice_agent, "assistant", "confirm", key="yes", text="ha") == output


async def test_voice_pagination_and_ordinal_are_bound_to_last_owned_view(voice_agent):
    from namoz_bot.domain.reminders import ReminderSpec, parse_time

    reminders = voice_agent[0]._adapters._reminders
    for number in range(5):
        await reminders.create(
            voice_agent[4].user_id,
            7,
            ReminderSpec(f"Kitob{number}", parse_time("09:00"), "daily"),
            f"item:{number}",
        )
    first = await command(voice_agent, "reminder", "list", key="list")
    second = await command(voice_agent, "reminder", "list", {"page_step": "next"}, key="next")
    assert first.data["page"] == 0 and second.data["page"] == 1
    target = second.data["entries"][0]["id"]
    prepared = await command(voice_agent, "reminder", "delete", {"ordinal": 1}, key="delete")
    assert prepared.data["draft"]["target_id"] == target


async def test_ordinal_without_recent_view_asks_for_target(voice_agent):
    result = await command(voice_agent, "reminder", "delete", {"ordinal": 2})
    assert result.status == "needs_input"


async def test_old_view_and_confirmation_expire_without_effect(voice_agent):
    from datetime import timedelta

    await command(voice_agent, "reminder", "list", key="list")
    assert (
        await voice_agent[2].get_last_view(voice_agent[4].user_id, NOW + timedelta(minutes=31))
        is None
    )
    await command(
        voice_agent,
        "reminder",
        "create",
        {"text": "Kitob", "time": "09:00", "kind": "daily"},
        key="draft",
    )
    voice_agent[0]._now = lambda: NOW + timedelta(hours=25)
    output = await command(voice_agent, "assistant", "confirm", key="yes", text="ha")
    assert output.status == "error" and output.effect == "none"
    assert not (await voice_agent[0]._adapters._reminders.page(voice_agent[4].user_id, 0))[0]


async def test_confirming_already_deleted_target_clears_draft(voice_agent):
    from namoz_bot.domain.reminders import ReminderSpec, parse_time

    service = voice_agent[0]._adapters._reminders
    target = await service.create(
        voice_agent[4].user_id, 7, ReminderSpec("Kitob", parse_time("09:00"), "daily"), "original"
    )
    await command(voice_agent, "reminder", "delete", {"target_id": target.id})
    await service.delete(voice_agent[4].user_id, target.id)
    output = await command(voice_agent, "assistant", "confirm", key="yes", text="ha")
    assert output.status == "unsupported" and output.effect == "none"
    assert await voice_agent[2].get_session(voice_agent[4].user_id, NOW) is None
