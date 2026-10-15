from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.profiles import RoleModelSetting
from namoz_bot.domain.workforce.tasks import TaskConflict, TaskPlan
from namoz_bot.infrastructure.orm import FinanceEntryRecord, WorkforceOutboxRecord
from namoz_bot.infrastructure.workforce.queue import SqlAlchemyTaskQueue
from namoz_bot.infrastructure.workforce.tasks import SqlAlchemyTaskStore
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant


@pytest.fixture
async def workforce(access_setup, store):
    profiles, access, user, _ = access_setup
    _, factory, _, _ = store
    await grant(profiles, user, user, "accounting", {"finance.income"})
    context = AgentContext(
        bot_id=123456,
        telegram_user_id=7,
        chat_id=7,
        user_id=user,
        message_time=NOW,
        region_code="Toshkent",
    )
    plan = TaskPlan(
        task_id=uuid4().hex[:20],
        revision=1,
        request_id="input1",
        context=context,
        permission=await access.require(user, "accounting", "finance.income"),
        role=profiles.roles.get("accounting"),
        models={
            r: RoleModelSetting(role_id=r, model_id="frozen-model")
            for r in ("assistant", "manager", "accounting")
        },
        selection=CapabilitySelection(
            role_id="accounting",
            capability_id="finance.income",
            parameters={
                "amount": 10000000,
                "currency": "UZS",
                "category": "oylik",
                "description": "Oylik",
            },
        ),
        transcript="Oylik tushdi",
        expires_at=NOW + timedelta(minutes=15),
    )
    current = [NOW]
    tasks = SqlAlchemyTaskStore(factory, clock=lambda: current[0])
    queue = SqlAlchemyTaskQueue(factory)
    return tasks, queue, access, plan, factory, profiles, current


async def test_exact_approval_deduplicates_and_foreign_old_expired_cards_deny(workforce):
    tasks, queue, _, plan, factory, _, current = workforce
    await tasks.save_plan(plan, expected_revision=None)
    assert not await queue.claim(now=NOW, limit=3, lease_seconds=180)
    foreign = plan.context.model_copy(update={"bot_id": 999})
    with pytest.raises(TaskConflict):
        await tasks.approve(plan.task_id, 1, foreign, "wrong", True)
    with pytest.raises(TaskConflict):
        await tasks.approve(plan.task_id, 2, plan.context, "old", True)
    queued = await tasks.approve(plan.task_id, 1, plan.context, "approve", True)
    assert queued.plan == plan and queued.status == "queued"
    await tasks.approve(plan.task_id, 1, plan.context, "approve", True)
    await tasks.approve(plan.task_id, 1, plan.context, "approve-again", True)
    async with factory() as session:
        assert len(list(await session.scalars(select(WorkforceOutboxRecord)))) == 1
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    assert len(await queue.claim(now=NOW, limit=3, lease_seconds=180)) == 1
    assert not await queue.claim(now=NOW, limit=3, lease_seconds=180)
    second = plan.model_copy(update={"task_id": uuid4().hex[:20], "request_id": "input2"})
    await tasks.save_plan(second, expected_revision=None)
    current[0] += timedelta(minutes=16)
    with pytest.raises(TaskConflict):
        await tasks.approve(second.task_id, 1, plan.context, "late", True)


async def test_reject_and_lost_lease_cannot_have_effect(workforce):
    tasks, queue, _, plan, _, _, current = workforce
    await tasks.save_plan(plan, expected_revision=None)
    cancelled = await tasks.approve(plan.task_id, 1, plan.context, "no", False)
    assert cancelled.status == "cancelled"
    assert not await queue.claim(now=NOW, limit=3, lease_seconds=180)
    second = plan.model_copy(update={"task_id": uuid4().hex[:20], "request_id": "input2"})
    await tasks.save_plan(second, expected_revision=None)
    await tasks.approve(second.task_id, 1, plan.context, "yes", True)
    claim = (await queue.claim(now=NOW, limit=3, lease_seconds=180))[0]
    current[0] += timedelta(seconds=181)
    with pytest.raises(TaskConflict):
        async with tasks.effect_scope(second.task_id, 1, claim.lease_token):
            pytest.fail("lost lease entered transaction")


async def test_expired_worker_cannot_mark_task_failed_or_commit_partial_effect(workforce):
    tasks, queue, access, plan, factory, _, current = workforce
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    claim = (await queue.claim(now=NOW, limit=3, lease_seconds=180))[0]
    from tests.integration.test_agent_sessions import finance_request

    with pytest.raises(RuntimeError):
        async with tasks.effect_scope(plan.task_id, 1, claim.lease_token) as tx:
            await access.require_in(tx, plan.context.user_id, "accounting", "finance.income")
            await tx.ledger.record(plan.context.user_id, finance_request(), "rollback", NOW)
            raise RuntimeError("crash before receipt")
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    current[0] += timedelta(seconds=181)
    await queue.fail(claim, permanent=True, now=current[0])
    assert (await tasks.get_owned(plan.task_id, plan.context)).status == "running"
