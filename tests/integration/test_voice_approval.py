from datetime import timedelta

import pytest
from sqlalchemy import select

from namoz_bot.application.main_agent import MainAgent
from namoz_bot.application.voice_approval import VoiceApproval
from namoz_bot.domain.agent_protocol import AgentDecision, AgentRevisionConflict
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.agent_sessions import SqlAlchemyAgentStore, SqlAlchemyAgentTransaction
from namoz_bot.infrastructure.orm import FinanceEntryRecord
from tests.integration.test_agent_sessions import store  # noqa: F401
from tests.integration.test_voice_agent_actions import NOW, command
from tests.integration.test_voice_agent_actions import voice_agent as _fixture

voice_agent = _fixture


async def preview(agent, domain, action, parameters=None, key="voice"):
    main, extractor, _, _, context, _ = agent
    extractor.decision = AgentDecision(
        domain=domain,
        action=action,
        parameters=parameters or {},
        transcript="Synthetic speech",
    )
    return await VoiceApproval(main).preview(
        context=context,
        request_id=key,
        audio=b"OggS-test",
        mime_type="audio/ogg",
    )


async def decide(agent, output, accept=True, key="button"):
    return await VoiceApproval(agent[0]).decide(
        context=agent[4],
        request_id=key,
        operation_id=output.operation_id,
        revision=output.data["revision"],
        accept=accept,
    )


async def test_review_survives_main_and_store_recreation_and_uses_exact_decision(voice_agent):
    output = await preview(
        voice_agent,
        "accounting",
        "expense",
        {
            "amount": 120000,
            "category": "kiyim",
            "description": "Kiyim",
            "currency": "UZS",
        },
    )
    main, extractor, _, factory, context, _ = voice_agent
    restarted = MainAgent(
        extractor,
        SqlAlchemyAgentStore(factory),
        adapters=main._adapters,
        now=lambda: NOW,
        voice_first=True,
    )
    extractor.decision = AgentDecision(domain="assistant", action="help", transcript="Different")
    result = await VoiceApproval(restarted).decide(
        context=context,
        request_id="button",
        operation_id=output.operation_id,
        revision=output.data["revision"],
        accept=True,
    )
    assert result.status == "done" and result.data["amount"] == 120000
    assert extractor.calls == 1


async def test_rejected_followup_restores_prior_then_approved_followup_completes(voice_agent):
    await command(
        voice_agent, "reminder", "create", {"text": "Kitob", "kind": "daily"}, key="draft"
    )
    main, _, repo, _, context, _ = voice_agent
    original = await repo.get_session(context.user_id, NOW)
    review = await preview(voice_agent, "reminder", "create", {"time": "08:00"})
    await decide(voice_agent, review, accept=False)
    restored = await repo.get_session(context.user_id, NOW)
    assert restored.parameters == original.parameters and restored.voice_review is None
    review = await preview(voice_agent, "reminder", "create", {"time": "09:00"}, key="correct")
    assert review.data["draft"]["parameters"]["text"] == "Kitob"
    result = await decide(voice_agent, review, key="correct-button")
    assert result.status == "done" and result.data["time"] == "09:00"
    assert (
        len(
            await main._adapters._reminders.repository.list_for_user(
                context.user_id,
                offset=0,
                limit=20,
            )
        )
        == 1
    )


async def test_expired_review_cannot_write_and_keeps_prior_draft(voice_agent):
    await command(voice_agent, "reminder", "create", {"text": "Kitob"}, key="draft")
    result = await preview(voice_agent, "reminder", "create", {"time": "09:00", "kind": "daily"})
    main, _, repo, _, context, _ = voice_agent
    main._now = lambda: NOW + timedelta(minutes=16)
    output = await decide(voice_agent, result)
    assert output.status == "error" and output.error_code == "stale_operation"
    pending = await repo.get_session(context.user_id, main._now())
    assert pending.parameters == {"text": "Kitob"} and pending.voice_review is None
    assert not await main._adapters._reminders.repository.list_for_user(
        context.user_id,
        offset=0,
        limit=20,
    )


async def test_old_bot_or_revision_cannot_approve_review(voice_agent):
    output = await preview(voice_agent, "settings", "set_daily", {"time": "07:00"})
    main, _, repo, _, context, _ = voice_agent
    for changed in [context.model_copy(update={"bot_id": 987654}), context]:
        failed = await VoiceApproval(main).decide(
            context=changed,
            request_id=f"bad:{changed.bot_id}",
            operation_id=output.operation_id,
            revision=output.data["revision"] if changed.bot_id != context.bot_id else 999,
            accept=True,
        )
        assert failed.status == "error"
    assert (await repo.get_session(context.user_id, NOW)).voice_review is not None
    assert (await decide(voice_agent, output)).status == "done"


async def test_effect_and_approval_receipt_roll_back_together(voice_agent, monkeypatch):
    output = await preview(
        voice_agent,
        "accounting",
        "expense",
        {
            "amount": 120000,
            "category": "kiyim",
            "description": "Kiyim",
            "currency": "UZS",
        },
    )
    original = SqlAlchemyAgentTransaction.save_receipt

    async def conflict(self, result):
        if result.effect == "committed":
            raise AgentRevisionConflict("synthetic receipt conflict")
        await original(self, result)

    monkeypatch.setattr(SqlAlchemyAgentTransaction, "save_receipt", conflict)
    assert (await decide(voice_agent, output)).status == "error"
    async with voice_agent[3]() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    assert (await voice_agent[2].get_session(voice_agent[4].user_id, NOW)).voice_review is not None
    monkeypatch.setattr(SqlAlchemyAgentTransaction, "save_receipt", original)
    assert (await decide(voice_agent, output, key="retry")).effect == "committed"


async def test_failed_new_voice_retires_previous_unapproved_command(voice_agent):
    old = await preview(
        voice_agent,
        "accounting",
        "expense",
        {
            "amount": 120000,
            "category": "kiyim",
            "description": "Kiyim",
            "currency": "UZS",
        },
    )
    voice_agent[1].error = ExternalServiceError("synthetic")
    assert (await preview(voice_agent, "settings", "set_daily", key="failed")).status == "error"
    assert (await decide(voice_agent, old)).status == "error"
    async with voice_agent[3]() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


@pytest.mark.parametrize("control", ["confirm", "resume"])
async def test_voice_control_does_not_resolve_prior_financial_clarification(voice_agent, control):
    main, extractor, _, factory, context, _ = voice_agent
    extractor.decision = AgentDecision(
        domain="accounting",
        action="expense",
        transcript="Synthetic uncertainty",
        parameters={
            "amount": 120000,
            "currency": "UZS",
            "category": "kiyim",
            "description": "Kiyim",
        },
        clarification="Bu xarajat amalga oshganmi?",
    )
    await main.respond(context=context, request_id="draft", text="synthetic")
    review = await preview(voice_agent, "assistant", control)
    result = await decide(voice_agent, review)
    assert result.status == "needs_input" and "amalga oshganmi" in result.question
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


@pytest.mark.parametrize("control", ["confirm", "resume"])
@pytest.mark.parametrize("uncertainty", ["clarification", "multiple_tasks"])
async def test_uncertain_voice_control_preserves_flags_and_cannot_execute_prior(
    voice_agent, control, uncertainty
):
    main, extractor, repo, _, context, _ = voice_agent
    await command(
        voice_agent,
        "reminder",
        "create",
        {"text": "Kitob", "time": "09:00", "kind": "daily"},
        key="prior",
    )
    flags = (
        {"clarification": "Qaysi amalni avval bajarish kerak?"}
        if uncertainty == "clarification"
        else {"multiple_tasks": True}
    )
    extractor.decision = AgentDecision(
        domain="assistant", action=control, transcript="Ha va boshqa amal", **flags
    )
    review = await VoiceApproval(main).preview(
        context=context, request_id="voice", audio=b"synthetic", mime_type="audio/ogg"
    )
    output = await decide(voice_agent, review)
    assert output.status == "needs_input"
    assert not await main._adapters._reminders.repository.list_for_user(
        context.user_id, offset=0, limit=20
    )
    assert review.data["draft"][uncertainty] == flags[uncertainty]
    pending = await repo.get_session(context.user_id, NOW)
    assert pending.voice_review is None and pending.missing_fields == ["confirmation"]
    extractor.decision = AgentDecision(domain="assistant", action="confirm", transcript="Ha")
    checked = await main.respond(context=context, request_id="check-prior", text="Ha")
    assert checked.status == "needs_confirmation"
    assert not await main._adapters._reminders.repository.list_for_user(
        context.user_id, offset=0, limit=20
    )
