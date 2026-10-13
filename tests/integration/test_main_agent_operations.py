from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from namoz_bot.application.main_agent import MainAgent
from namoz_bot.domain.agent_protocol import AgentContext, AgentDecision
from namoz_bot.infrastructure.orm import FinanceEntryRecord, ReminderRecord
from tests.integration.test_agent_sessions import NOW, store  # noqa: F401


class Extractor:
    def __init__(self):
        self.decision = AgentDecision(domain="assistant", action="help", transcript="test")
        self.calls = 0
        self.pending = None
        self.error = None

    async def extract(self, **kwargs):
        self.calls += 1
        self.pending = kwargs["pending"]
        if self.error:
            raise self.error
        return self.decision


def decision(domain, action, **params):
    return AgentDecision(domain=domain, action=action, transcript="test", parameters=params)


@pytest.fixture
def agent(store):  # noqa: F811
    repo, factory, user, _ = store
    extractor = Extractor()
    context = AgentContext(
        bot_id=123456,
        telegram_user_id=7,
        chat_id=7,
        user_id=user,
        message_time=NOW,
        region_code="Toshkent",
    )
    main = MainAgent(extractor, repo, now=lambda: NOW)
    return main, extractor, repo, factory, context


async def respond(agent, chosen, key="r1", text="test"):
    main, extractor, _, _, context = agent
    extractor.decision = chosen
    return await main.respond(context=context, request_id=key, text=text)


async def test_finance_followup_commits_once_and_replay_skips_extraction(agent):
    main, extractor, repo, factory, context = agent
    first = await respond(
        agent,
        decision("accounting", "expense", category="kiyim", description="Kiyim", currency="UZS"),
    )
    assert first.status == "needs_input"
    result = await respond(agent, decision("accounting", "expense", amount=120000), "r2")
    assert result.status == "done" and result.effect == "committed"
    assert result.data["balance"] == -120000
    repeated = await main.respond(context=context, request_id="r2", text="different")
    assert repeated.operation_id == result.operation_id
    assert extractor.calls == 2
    assert await repo.get_session(context.user_id, NOW) is None
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_reminder_followup_preserves_date_and_requires_button(agent):
    main, _, repo, factory, context = agent
    date = (NOW + timedelta(days=1)).date().isoformat()
    first = await respond(
        agent, decision("reminder", "create", text="Uchrashuv", date=date, kind="once")
    )
    assert first.status == "needs_input" and "time" in first.missing_fields
    ready = await respond(agent, decision("reminder", "create", time="09:00"), "r2")
    assert ready.status == "needs_confirmation"
    assert ready.data["draft"]["date"] == date
    plain_yes = await respond(agent, decision("assistant", "clarify"), "r3", text="ha")
    assert plain_yes.status == "needs_confirmation"
    async with factory() as session:
        assert not list(await session.scalars(select(ReminderRecord)))
    pending = await repo.get_session(context.user_id, NOW)
    saved = await main.confirm(
        context=context,
        request_id="save",
        operation_id=pending.operation_id,
        revision=pending.revision,
    )
    assert saved.status == "done" and saved.effect == "committed"
    await main.confirm(
        context=context,
        request_id="save",
        operation_id=pending.operation_id,
        revision=pending.revision,
    )
    async with factory() as session:
        assert len(list(await session.scalars(select(ReminderRecord)))) == 1


async def test_domain_switch_and_multiple_tasks_do_not_discard_or_execute(agent):
    _, _, repo, factory, context = agent
    await respond(agent, decision("reminder", "create", text="Uchrashuv"))
    before = await repo.get_session(context.user_id, NOW)
    switch = await respond(
        agent,
        decision(
            "accounting",
            "expense",
            amount=120000,
            currency="UZS",
            category="kiyim",
            description="Kiyim",
        ),
        "r2",
    )
    assert switch.status == "needs_input" and switch.missing_fields == ["active_task"]
    assert (await repo.get_session(context.user_id, NOW)).operation_id == before.operation_id
    multi = AgentDecision(
        domain="assistant", action="clarify", transcript="two tasks", multiple_tasks=True
    )
    result = await respond(agent, multi, "r3")
    assert result.status == "needs_input"
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


@pytest.mark.parametrize(
    "params",
    [
        {"amount": 120000, "currency": "OTHER"},
        {"amount": 120000, "currency": "UZS", "date": "2027-01-01"},
    ],
)
async def test_currency_and_future_rules_preserved(agent, params):
    result = await respond(
        agent, decision("accounting", "expense", category="kiyim", description="Kiyim", **params)
    )
    assert result.status in {"unsupported", "needs_input"}
    async with agent[3]() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


async def test_report_never_creates_entry(agent):
    result = await respond(
        agent, decision("accounting", "report", month="2026-10", report_type="expense")
    )
    assert result.status == "done" and result.data["expense"] == 0
    async with agent[3]() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


async def test_provider_error_preserves_draft(agent):
    from namoz_bot.domain.errors import ExternalServiceError

    main, extractor, repo, _, context = agent
    await respond(agent, decision("reminder", "create", text="Kitob"))
    before = await repo.get_session(context.user_id, NOW)
    extractor.error = ExternalServiceError("failed")
    result = await main.respond(context=context, request_id="r2", text="09:00")
    assert result.status == "error"
    assert (await repo.get_session(context.user_id, NOW)).model_dump() == before.model_dump()


async def test_stale_confirmation_cannot_commit(agent):
    main, _, repo, _, context = agent
    ready = await respond(
        agent, decision("reminder", "create", text="Kitob", time="09:00", kind="daily")
    )
    old = await repo.get_session(context.user_id, NOW)
    await respond(agent, decision("reminder", "create", time="10:00"), "r2")
    result = await main.confirm(
        context=context, request_id="save", operation_id=ready.operation_id, revision=old.revision
    )
    assert result.status == "error" and result.error_code == "stale_operation"


async def test_confirmation_revalidates_past_time(agent):
    main, _, repo, _, context = agent
    day = NOW.date().isoformat()
    await respond(
        agent, decision("reminder", "create", text="Kitob", time="20:00", date=day, kind="once")
    )
    pending = await repo.get_session(context.user_id, NOW)
    main._now = lambda: datetime(2026, 10, 13, 16, tzinfo=UTC)
    result = await main.confirm(
        context=context,
        request_id="save",
        operation_id=pending.operation_id,
        revision=pending.revision,
    )
    assert result.status == "needs_input" and "date" in result.missing_fields


async def test_prayer_uses_region_date_and_offsets(agent):
    from namoz_bot.application.agent_adapters import AgentAdapters
    from namoz_bot.application.schedules import ScheduleService
    from namoz_bot.domain.models import PrayerOffsets, PrayerSchedule, PrayerTimes

    class Provider:
        async def get_for_date(self, region, date):
            assert region == "Toshkent" and date.isoformat() == "2026-10-14"
            return PrayerSchedule(
                date,
                region,
                "Toshkent",
                PrayerTimes("05:00", "06:00", "12:00", "15:00", "18:00", "19:00"),
            )

    agent[0]._adapters = AgentAdapters(ScheduleService(Provider()))
    context = agent[4].model_copy(update={"offsets": PrayerOffsets(shom=5)})
    agent[1].decision = decision("prayer", "schedule", date="2026-10-14", prayer="shom")
    output = await agent[0].respond(context=context, request_id="prayer", text="Ertaga shom?")
    assert output.data["time"] == "18:05"


async def test_restart_resumes_same_draft(agent):
    from namoz_bot.infrastructure.agent_sessions import SqlAlchemyAgentStore

    first = await respond(agent, decision("reminder", "create", text="Kitob"))
    restarted = MainAgent(agent[1], SqlAlchemyAgentStore(agent[3]), now=lambda: NOW)
    output = await restarted.resume(context=agent[4], request_id="resume")
    assert output.operation_id == first.operation_id
    assert output.status == "needs_input"


async def test_invalid_merge_keeps_pending_and_returns_safe_error(agent):
    date = (NOW + timedelta(days=1)).date().isoformat()
    await respond(agent, decision("reminder", "create", text="Kitob", kind="once", date=date))
    before = await agent[2].get_session(agent[4].user_id, NOW)
    output = await respond(agent, decision("reminder", "create", weekdays=[1]), "invalid")
    assert output.status == "error"
    assert (await agent[2].get_session(agent[4].user_id, NOW)).model_dump() == before.model_dump()


async def test_cancel_result_uses_original_operation_identity(agent):
    output = await respond(agent, decision("reminder", "create", text="Kitob"))
    cancelled = await agent[0].respond(context=agent[4], request_id="cancel", text="Bekor qil")
    assert cancelled.status == "cancelled" and cancelled.operation_id == output.operation_id


async def test_service_failure_is_retryable_not_invalid_input(agent):
    from namoz_bot.application.agent_adapters import AgentAdapters
    from namoz_bot.domain.errors import ExternalServiceError

    class FailedAdapters(AgentAdapters):
        async def prepare(self, request):
            raise ExternalServiceError("Temporary provider failure")

    agent[0]._adapters = FailedAdapters()
    output = await respond(agent, decision("prayer", "schedule"))
    assert output.status == "error" and output.retryable
    assert output.error_code == "provider_unavailable"


async def test_resume_does_not_lose_pending_clarification(agent):
    agent[1].decision = decision(
        "accounting",
        "expense",
        amount=120000,
        currency="UZS",
        category="kiyim",
        description="Kiyim",
    ).model_copy(update={"clarification": "Bu xarajat amalga oshdimi?"})
    first = await agent[0].respond(context=agent[4], request_id="first", text="test")
    assert first.status == "needs_input"
    output = await agent[0].resume(context=agent[4], request_id="resume")
    assert output.status == "needs_input" and output.question


async def test_finance_yes_answers_clarification_and_commits(agent):
    complete = decision(
        "accounting",
        "expense",
        amount=120000,
        currency="UZS",
        category="kiyim",
        description="Kiyim",
    )
    agent[1].decision = complete.model_copy(update={"clarification": "Bu xarajat amalga oshdimi?"})
    first = await agent[0].respond(context=agent[4], request_id="first", text="test")
    assert first.status == "needs_input"
    agent[1].decision = complete
    output = await agent[0].respond(context=agent[4], request_id="yes", text="ha")
    assert output.status == "done" and output.effect == "committed"
    assert output.data["balance"] == -120000 and agent[1].calls == 2
