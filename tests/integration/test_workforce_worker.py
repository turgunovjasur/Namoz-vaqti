import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.workforce.execution import TaskExecutionService
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.domain.workforce.tasks import TaskConflict
from namoz_bot.infrastructure.orm import FinanceEntryRecord
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant
from tests.integration.test_workforce_tasks import workforce as workforce


async def approved(workforce):
    tasks, queue, _, plan, _, _, _ = workforce
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    return (await queue.claim(now=NOW, limit=3, lease_seconds=180))[0]


async def test_saved_effect_survives_restart_and_is_not_repeated(workforce):
    tasks, queue, access, plan, factory, _, current = workforce
    claim = await approved(workforce)
    executor = TaskExecutionService(tasks, access, build_capability_registry())
    first = await executor.run(claim)
    assert first.service_result.effect == "committed"
    current[0] += timedelta(seconds=181)
    recovered = (await queue.claim(now=current[0], limit=3, lease_seconds=180))[0]
    second = await TaskExecutionService(tasks, access, build_capability_registry()).run(recovered)
    assert second.service_result == first.service_result
    async with factory() as session:
        entries = list(await session.scalars(select(FinanceEntryRecord)))
        assert len(entries) == 1 and entries[0].amount == 10000000
    with pytest.raises(TaskConflict):
        async with tasks.effect_scope(plan.task_id, 1, claim.lease_token):
            pytest.fail("old worker retained lease")


async def test_revoke_between_approval_and_execution_blocks_effect(workforce):
    tasks, _, access, plan, factory, profiles, _ = workforce
    claim = await approved(workforce)
    await grant(profiles, plan.context.user_id, plan.context.user_id, "accounting", set())
    with pytest.raises(AccessDenied):
        await TaskExecutionService(tasks, access, build_capability_registry()).run(claim)
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


async def test_concurrent_postgres_workers_have_one_effect(workforce):
    tasks, queue, access, plan, factory, _, _ = workforce
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL claims race")
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    batches = await asyncio.gather(
        *(queue.claim(now=NOW, limit=3, lease_seconds=180) for _ in range(2))
    )
    assert sum(map(len, batches)) == 1
    claim = next(c for batch in batches for c in batch)
    await TaskExecutionService(tasks, access, build_capability_registry()).run(claim)
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_shutdown_cancels_running_job_and_restart_can_reclaim(workforce):
    from namoz_bot.application.workforce.worker import Worker

    tasks, queue, _, plan, _, _, current = workforce
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    entered = asyncio.Event()

    class WaitingRunner:
        async def run(self, claim):
            entered.set()
            await asyncio.Event().wait()

    worker = Worker(queue, WaitingRunner())
    running = asyncio.create_task(worker.run_once(NOW))
    await entered.wait()
    await worker.close()
    with pytest.raises(asyncio.CancelledError):
        await running
    current[0] += timedelta(seconds=181)
    assert len(await queue.claim(now=current[0], limit=3, lease_seconds=180)) == 1


async def test_review_worker_failure_never_says_committed_expense_was_not_saved(workforce):
    from namoz_bot.infrastructure.orm import WorkforceOutboxRecord

    tasks, queue, access, _, factory, _, _ = workforce
    claim = await approved(workforce)
    await TaskExecutionService(tasks, access, build_capability_registry()).run(claim)
    await queue.fail(claim, permanent=True, now=NOW)
    async with factory() as session:
        failure = await session.scalar(
            select(WorkforceOutboxRecord).where(WorkforceOutboxRecord.kind == "failure")
        )
        assert "saqlandi" in failure.payload["text"].lower()
        assert "bajarilmadi" not in failure.payload["text"].lower()
