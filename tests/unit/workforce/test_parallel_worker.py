import asyncio
from uuid import uuid4

import pytest

from namoz_bot.application.workforce.worker import Worker
from namoz_bot.domain.workforce.tasks import ClaimedTask, TaskRevision
from tests.integration.test_agent_sessions import NOW
from tests.unit.skills.test_native_skills import plan


async def test_dispatch_refills_slots_while_slow_job_keeps_running():
    claims = [
        ClaimedTask(
            task=TaskRevision(
                plan=plan().model_copy(update={"task_id": uuid4().hex[:20]}), status="running"
            ),
            lease_token=str(i),
        )
        for i in range(3)
    ]
    started = [asyncio.Event() for _ in claims]
    release = [asyncio.Event() for _ in claims]

    class Queue:
        async def claim(self, *, limit, **kwargs):
            result = pending[:limit]
            del pending[:limit]
            return result

        async def heartbeat(self, *args):
            return True

        async def fail(self, *args, **kwargs):
            pytest.fail("Unexpected worker failure")

    class Runner:
        async def run(self, claim):
            i = int(claim.lease_token)
            started[i].set()
            await release[i].wait()

    pending = list(claims)
    worker = Worker(Queue(), Runner(), max_concurrency=2)
    try:
        await asyncio.wait_for(worker.dispatch(NOW), 1)
        await asyncio.wait_for(asyncio.gather(started[0].wait(), started[1].wait()), 1)
        await worker.dispatch(NOW)
        assert not started[2].is_set()
        release[1].set()
        for _ in range(10):
            await asyncio.sleep(0)
        await worker.dispatch(NOW)
        await asyncio.wait_for(started[2].wait(), 1)
        assert not release[0].is_set()
    finally:
        await worker.close()
